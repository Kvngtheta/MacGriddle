# 🍔 MacGriddle
This was originally was created to be gag, but can also deployed to a raspberry pi or other similar devices to be used on remote testing sites for pentesting purposes.

# ***DISCLOSURE***
This is a simple a flask application and contains multiple vulnerabilities  (RUN AT YOUR OWN RISK!). Do not use for production environements


How To:

# MAC SPOOFING

Select the device that contains the mac you want to change
Input the MAC that you want to be spoofed
Input time duration

# REMOTE SHELL

This remote shell:

Has no authentication
Runs any system command with the same privileges as the Flask app (root if run with sudo)
Should never be exposed publicly without access controls

There is absolutely no authentication mechanisms in place! Only use for testing purposes!!!
