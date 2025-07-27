# -*- coding: utf-8 -*-
import subprocess
import threading
from flask import Flask, request, jsonify, render_template_string
import psutil
import netifaces as ni

ADMIN_PORT = 9090
API_PORT = 8080
STATUS_PORT = 7071

THEME = {
    'bg': '#FFC72C',
    'accent': '#DA291C',
    'text': '#000000'
}

spoofed_devices = {}

admin_app = Flask('MacGriddle-Admin')
api_app = Flask('MacGriddle-API')
status_app = Flask('MacGriddle-Status')

def get_connected_devices():
    try:
        output = subprocess.check_output("ip neigh", shell=True).decode()
        devices = []
        for line in output.strip().split("\n"):
            parts = line.split()
            if len(parts) >= 5 and parts[4] != "FAILED":
                devices.append({'ip': parts[0], 'mac': parts[4], 'dev': parts[2]})
        return devices
    except Exception:
        return []

def get_mac(interface):
    try:
        return subprocess.check_output(f"cat /sys/class/net/{interface}/address", shell=True).decode().strip()
    except Exception:
        return "unknown"

def get_interface_macs():
    macs = {}
    for iface in psutil.net_if_addrs():
        try:
            mac = get_mac(iface)
            macs[iface] = mac
        except:
            macs[iface] = "N/A"
    return macs

def get_interface_status():
    interfaces = psutil.net_if_addrs().keys()
    mac_info = {}
    for iface in interfaces:
        if iface != 'lo':
            current_mac = get_mac(iface)
            original_mac = spoofed_devices.get(iface, {}).get('original', current_mac)
            spoofed = spoofed_devices.get(iface, {}).get('current', None)
            mac_info[iface] = {
                'original_mac': original_mac,
                'current_mac': spoofed if spoofed else current_mac,
                'is_spoofed': spoofed is not None and spoofed != original_mac
            }
    return mac_info

def spoof_mac(interface, new_mac, duration):
    try:
        original_mac = get_mac(interface)
        subprocess.run(["sudo", "ip", "link", "set", interface, "down"])
        subprocess.run(["sudo", "ip", "link", "set", interface, "address", new_mac])
        subprocess.run(["sudo", "ip", "link", "set", interface, "up"])
        spoofed_devices[interface] = {'original': original_mac, 'current': new_mac}

        if duration > 0:
            threading.Timer(duration * 60, revert_mac, args=[interface, original_mac]).start()
        return True
    except Exception:
        return False

def revert_mac(interface, original_mac=None):
    try:
        if not original_mac:
            original_mac = spoofed_devices.get(interface, {}).get('original')
        if original_mac:
            subprocess.run(["sudo", "ip", "link", "set", interface, "down"])
            subprocess.run(["sudo", "ip", "link", "set", interface, "address", original_mac])
            subprocess.run(["sudo", "ip", "link", "set", interface, "up"])
            spoofed_devices.pop(interface, None)
    except Exception:
        pass

@admin_app.route("/")
def admin_index():
    interfaces = list(psutil.net_if_addrs().keys())
    devices = get_connected_devices()
    macs = get_interface_macs()
    ip = ni.ifaddresses('eth0')[ni.AF_INET][0]['addr'] if 'eth0' in ni.interfaces() else 'N/A'
    uptime = subprocess.getoutput("uptime -p")
    return render_template_string("""<html>
    <body style="background-color: {{theme.bg}}; color: {{theme.text}}; font-family: sans-serif;">
    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
      <h1 style="color: {{theme.accent}};">MacGriddle - Admin Panel</h1>
      <div style="text-align: right;">
        <h3>MAC Status</h3>
        {% for iface, data in spoofed.items() %}
          <p><b>{{iface}}</b><br>
          Original: {{data.original}}<br>
          Spoofed: {{data.current}}</p>
        {% endfor %}
      </div>
    </div>
    <p><b>IP:</b> {{ip}} | <b>Uptime:</b> {{uptime}}</p>
    <h2>Interfaces & MACs</h2>
    <ul>
    {% for iface in interfaces %}
      <li>{{iface}} - <b>{{macs[iface]}}</b></li>
    {% endfor %}
    </ul>
    <h2>MAC Spoofing</h2>
    <form method="post" action="/mac">
      Interface:
      <select name="iface">
        {% for iface in interfaces %}
          <option value="{{iface}}">{{iface}}</option>
        {% endfor %}
      </select><br>
      New MAC: <input name="mac"><br>
      Duration (min): <input name="duration"><br>
      <input type="submit" value="Spoof MAC">
    </form>
    <form method="post" action="/revert">
      <h3>Revert MAC</h3>
      <select name="iface">
        {% for iface in spoofed %}
          <option value="{{iface}}">{{iface}}</option>
        {% endfor %}
      </select>
      <input type="submit" value="Revert">
    </form>
    <h2>Remote Shell</h2>
    <form method="post" action="/exec">
      Command: <input name="cmd" size="60"><br>
      <input type="submit">
    </form>
    <pre>{{output}}</pre>
    <h2>Connected Devices</h2>
    <ul>
    {% for d in devices %}
      <li>{{d.ip}} - {{d.mac}} ({{d.dev}})</li>
    {% endfor %}
    </ul>
    </body></html>""", interfaces=interfaces, macs=macs, spoofed=spoofed_devices, ip=ip, uptime=uptime, devices=devices, output="", theme=THEME)

@admin_app.route("/exec", methods=["POST"])
def run_shell():
    cmd = request.form.get("cmd")
    try:
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True)
    except subprocess.CalledProcessError as e:
        output = e.output
    return admin_index().replace("<pre></pre>", f"<pre>{output}</pre>")

@admin_app.route("/mac", methods=["POST"])
def admin_mac():
    iface = request.form.get("iface")
    mac = request.form.get("mac")
    duration = int(request.form.get("duration", 0))
    success = spoof_mac(iface, mac, duration)
    result = "Success" if success else "Failed"
    return admin_index().replace("<pre></pre>", f"<pre>{result}</pre>")

@admin_app.route("/revert", methods=["POST"])
def revert_route():
    iface = request.form.get("iface")
    revert_mac(iface)
    return admin_index().replace("<pre></pre>", "<pre>MAC reverted</pre>")

@api_app.route("/devices", methods=["GET"])
def api_devices():
    return jsonify(get_connected_devices())

@api_app.route("/spoof", methods=["POST"])
def api_spoof():
    data = request.json
    iface = data.get("interface")
    new_mac = data.get("mac")
    duration = int(data.get("duration", 0))
    if iface == "all":
        result = {i: "ok" if spoof_mac(i, new_mac, duration) else "fail" for i in psutil.net_if_addrs() if i != "lo"}
        return jsonify({"status": result})
    else:
        success = spoof_mac(iface, new_mac, duration)
        return jsonify({"status": "ok" if success else "fail"})

@status_app.route("/mac-status", methods=["GET"])
def mac_status():
    return jsonify(get_interface_status())

@status_app.route("/")
def mac_status_ui():
    macs = get_interface_status()
    return render_template_string("""<html><body style="background-color: {{theme.bg}}; color: {{theme.text}}; font-family: sans-serif;">
    <h1 style="color: {{theme.accent}};">MacGriddle - MAC Status</h1>
    <table border="1" cellpadding="5" cellspacing="0">
      <tr><th>Interface</th><th>Original MAC</th><th>Current MAC</th><th>Spoofed?</th></tr>
      {% for iface, info in macs.items() %}
        <tr>
          <td>{{iface}}</td>
          <td>{{info.original_mac}}</td>
          <td>{{info.current_mac}}</td>
          <td>{{"✅" if info.is_spoofed else "❌"}}</td>
        </tr>
      {% endfor %}
    </table>
    </body></html>""", macs=macs, theme=THEME)

# Run all apps
threading.Thread(target=lambda: admin_app.run(host="0.0.0.0", port=ADMIN_PORT)).start()
threading.Thread(target=lambda: api_app.run(host="0.0.0.0", port=API_PORT)).start()
threading.Thread(target=lambda: status_app.run(host="0.0.0.0", port=STATUS_PORT)).start()
