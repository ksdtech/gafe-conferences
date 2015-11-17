# Save a copy of this file as config_dev.py to run on dev_appserver
# Save a copy of this file as config_gae.py to run on Google App Engine

# Customize this to your GAFE domain
gafe_domain = 'example.org'

# Change protocol, hostname and port to "gafe-conferences.appspot.com", etc when you deploy!

# These are stored in conventional Flask config variables:
# 'PREFERRED_URL_SCHEME'
# 'SERVER_NAME'
protocol = 'http'
hostname = 'localhost'
port = 8080

secret_key = 'a-very-long-random-key-used-to-hash-csrf-tokens'
friendly_name = 'KSD Conference System'
support_email = 'webmaster@kentfieldschools.org'
reminders_expire = 60
