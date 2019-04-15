# ASM3 site definitions

# The base URL to the ASM installation as seen by the client (should not end with /)
BASE_URL = "{{ asm_base_url }}"

# The URL to asm's service endpoint to be shown in online forms screen
SERVICE_URL = BASE_URL + "/service"

# The language to use before a locale has been configured
# in the database
LOCALE = "en"

# The timezone offset to use before one has been configured
# in the database (+/- server clock offset, NOT UTC)
TIMEZONE = 0

# Where ASM directs log output to, one of:
# stderr  - the standard error stream
# syslog  - the UNIX syslogger (to LOCAL3 facility)
# ntevent - the Windows event logger
# <file>  - The path to a file to log to
LOG_LOCATION = "{{ asm_sitedefs.log_location }}"

# Include debug messages when logging - set to False
# to disable debug messages
LOG_DEBUG = False

# Database info
DB_TYPE = "{{ asm_db.type }}" # MYSQL, POSTGRESQL, SQLITE or DB2
DB_HOST = "{{ asm_db.host }}"
DB_PORT = {{ asm_db.port }}
DB_USERNAME = "{{ asm_db.user }}"
DB_PASSWORD = "{{ asm_db.pass }}"
DB_NAME = "{{ asm_db.name }}"

# If you want to maintain compatibility with an ASM2 client
# accessing your database, setting this will have ASM3
# update the primarykey table that ASM2 needs
DB_HAS_ASM2_PK_TABLE = False

# If False, HTML entities (all unicode chars) will be stored as is in the database.
# (this is better for databases with non Unicode collation/storage and less of
#  a security risk for Unicode SQL/XSS attacks)
# If True, HTML entities will be decoded to Unicode before storing in the database
# (storage is more efficient as UTF8 should be used for 2 bytes/char instead of 5)
DB_DECODE_HTML_ENTITIES = False

# If set, all calls to db.execute will be logged to the file
# named. Use {database} to substitute database name.
DB_EXEC_LOG = ""

# Produce an EXPLAIN for each query in the log before running it
DB_EXPLAIN_QUERIES = False

# Record the time taken to run each query
DB_TIME_QUERIES = False

# If DB_TIME_QUERIES is on, only log queries that take longer
# than X seconds to run (or 0 to log all)
DB_TIME_LOG_OVER = 0

# Time out queries that take longer than this (ms) to run
DB_TIMEOUT = 0

# URLs for ASM services
URL_NEWS = "https://sheltermanager.com/repo/asm_news.html"
URL_REPORTS = "https://sheltermanager.com/repo/reports.txt"

# Deployment type, wsgi or fcgi
DEPLOYMENT_TYPE = "wsgi"

# Whether the session cookie should be secure (only valid for https)
SESSION_SECURE_COOKIE = True

# Output debug info on sessions
SESSION_DEBUG = False

# The host/port that memcached is running on if it is to be used.
# If memcache is not available, an in memory dictionary will be
# used instead.
MEMCACHED_SERVER = "127.0.0.1:11211"
#MEMCACHED_SERVER = ""

# Where to store media files.
# database - media files are base64 encoded in the dbfs.content db column
# file - media files are stored in a folder
# s3 - media files are stored in amazon s3
DBFS_STORE = "{{ asm_sitedefs.dbfs_store }}"

# DBFS_STORE = file: The folder where media files are stored.
# It must exist and ASM must have write permissions. It should never end with a /
DBFS_FILESTORAGE_FOLDER = "{{ asm_data }}/media"

# DBFS_STORE = s3: The S3 bucket to store media in
DBFS_S3_BUCKET = ""

# The directory to use to cache elements on disk. Must already exist
# as the application will not attempt to create it.
DISK_CACHE = "{{ asm_data }}/cache"

# Cache results of the most common, less important queries for
# a short period (60 seconds) in the disk cache to help performance.
# These queries include shelterview animals and main screen links)
CACHE_COMMON_QUERIES = False

# Cache service call responses on the server side according
# to their max-age headers in the disk cache
CACHE_SERVICE_RESPONSES = False

# If EMAIL_ERRORS is set to True, all errors from the site
# are emailed to ADMIN_EMAIL and the user is given a generic
# error page. If set to False, debug information is output.
EMAIL_ERRORS = False
ADMIN_EMAIL = "{{ asm_sitedefs.admin_email }}"

# If MINIFY_JS is set to True, minified versions of the javascript
# files will be generated at build/deploy time and the handler
# in html.py will reference them instead
MINIFY_JS = False

# If ROLLUP_JS is set to True, all javascript files will be rolled
# up into a single file before sending to the client (combine
# with MINIFY_JS for smallest payload in a single request)
ROLLUP_JS = False

# Only allow hotlinks to the animal_image and extra_image
# service calls from this domain, or comma separated list of domains
IMAGE_HOTLINKING_ONLY_FROM_DOMAIN = ""

# Use Transfer-Encoding: chunked for large files. Note that
# this does not work with mod_wsgi. Turning it off will cause
# web.py to buffer the output, which can cause problems with
# dumps of large databases.
LARGE_FILES_CHUNKED = True

# QR code provider. "url" and "size" tokens will be substituted
QR_IMG_SRC = "//chart.googleapis.com/chart?cht=qr&chl=%(url)s&chs=%(size)s"

# Shell command to use to compress PDFs
SCALE_PDF_DURING_ATTACH = False
SCALE_PDF_CMD = "convert -density 120 -quality 60 %(input)s -compress Jpeg %(output)s"
#SCALE_PDF_CMD = "pdftk %(input)s output %(output)s compress"
#SCALE_PDF_CMD = "gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/screen -dNOPAUSE -dQUIET -dBATCH -sOutputFile=%(output)s %(input)s"

# Shell command to convert HTML to PDF
HTML_TO_PDF = "wkhtmltopdf --orientation %(orientation)s %(papersize)s %(input)s %(output)s"
#HTML_TO_PDF = "html2pdf %(input)s %(output)s"

# Target for viewing an address on a map, {0} is the address
MAP_LINK = "https://www.openstreetmap.org/search?query={0}"

# Map provider for rendering maps on the client, can be "osm" or "google"
MAP_PROVIDER = "osm"
MAP_PROVIDER_KEY = ""       # For google, the API key to use when making map requests
OSM_MAP_TILES = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"

GEO_PROVIDER = "{{ asm_sitedefs.geo_provider }}"  # Geocode provider to use - nominatim or google
GEO_PROVIDER_KEY = "{{ asm_sitedefs.geo_provider_key }}" # For google, the API key to use when making geocoding requests
GEO_SMCOM_URL = ""
GEO_BATCH = True            # Whether or not to try and lookup geocodes as part of the batch
GEO_LIMIT = 100             # How many geocodes to lookup as part of the batch
GEO_LOOKUP_TIMEOUT = 5      # Timeout when doing geocode lookups
GEO_SLEEP_AFTER = 1         # Sleep for seconds after a request to throttle (nominatim has a 1/s limit)

# Enable the database field on login and allow login to multiple databases
MULTIPLE_DATABASES = False
MULTIPLE_DATABASES_TYPE = "map"
MULTIPLE_DATABASES_MAP = {
    #"alias": { "dbtype": "MYSQL", "host": "localhost", "port": 3306, "username": "root", "password": "root", "database": "asm" }
}

# FTP hosts and URLs for third party publishing services
ADOPTAPET_FTP_HOST = "autoupload.adoptapet.com"
ANIBASE_BASE_URL = ""
ANIBASE_API_USER = ""
ANIBASE_API_KEY = ""
FOUNDANIMALS_FTP_HOST = ""
FOUNDANIMALS_FTP_USER = ""
FOUNDANIMALS_FTP_PASSWORD = ""
HELPINGLOSTPETS_FTP_HOST = "www.helpinglostpets.com"
MADDIES_FUND_TOKEN_URL = ""
MADDIES_FUND_UPLOAD_URL = ""
PETFINDER_FTP_HOST = "members.petfinder.com"
PETRESCUE_URL = ""
RESCUEGROUPS_FTP_HOST = "ftp.rescuegroups.org"
SMARTTAG_FTP_HOST = "ftp.idtag.com"
SMARTTAG_FTP_USER = ""
SMARTTAG_FTP_PASSWORD = ""
PETTRAC_UK_POST_URL = "https://online.pettrac.com/registration/onlineregistration.aspx"
PETLINK_BASE_URL = ""
PETSLOCATED_FTP_HOST = "ftp.petslocated.com"
PETSLOCATED_FTP_USER = ""
PETSLOCATED_FTP_PASSWORD = ""
VETENVOY_US_VENDOR_USERID = ""
VETENVOY_US_VENDOR_PASSWORD = ""
VETENVOY_US_BASE_URL = "https://www.vetenvoy.info/"
VETENVOY_US_SYSTEM_ID = "20"
VETENVOY_US_HOMEAGAIN_RECIPIENTID = ""
VETENVOY_US_AKC_REUNITE_RECIPIENTID = ""

# Override the html publishDir with a fixed value and forbid
# editing in the UI.
# {alias} will be substituted for the current database alias
# {database} the current database name
# {username} the current database username.
# MULTIPLE_DATABASES_PUBLISH_DIR = "/home/somewhere/{alias}"
MULTIPLE_DATABASES_PUBLISH_DIR = ""

# The URL to show in the UI when publish dir is overridden
# MULTIPLE_DATABASES_PUBLISH_URL = "http://yoursite.com/{alias}"
MULTIPLE_DATABASES_PUBLISH_URL = ""

# Override the HTML/FTP upload credentials. Setting this
# turns on FTP upload and hides those configuration fields in the UI
#MULTIPLE_DATABASES_PUBLISH_FTP = { "host": "ftp.host.com", "user": "user", "pass": "pass", "port": 21, "chdir": "/home/{alias}", "passive": True }
MULTIPLE_DATABASES_PUBLISH_FTP = None

# Options available under the share button
SHARE_BUTTON = "shareweb,shareemail"

# Type of electronic signing device available
ELECTRONIC_SIGNATURES = "touch"

# If you want a forgotten password link on the login page,
# the URL it should link to
FORGOTTEN_PASSWORD = ""

# The text to show on the link
FORGOTTEN_PASSWORD_LABEL = ""

# If you have an emergency notice you'd like displaying on the
# login and home screens, set a filename here for the content
# (if the file does not exist or has no content, nothing will
# be displayed).
EMERGENCY_NOTICE = ""

# SMTP_SERVER = { "sendmail": False, "host": "mail.yourdomain.com", "port": 25, "username": "userifauth", "password": "passifauth", "usetls": False }
# SMTP_SERVER = { "sendmail": False, "host": "mail.yourdomain.com", "port": 25, "username": "", "password": "", "usetls": False }
SMTP_SERVER = { "sendmail": True }

# The from address for all outgoing emails. The email address configured
# in the database will be used as the Reply-To header to avoid
# any issues with DKIM/SPF/DMARC spoofing
# substitutions:
# {organisation} organisation name
# {database} database name
# {alias} database alias
FROM_ADDRESS = "{{ asm_sitedefs.admin_email }}"

# URLs to access manuals and help documentation
MANUAL_HTML_URL = "static/pages/manual/index.html"
MANUAL_FAQ_URL = "static/pages/manual/faq.html"
MANUAL_PDF_URL = ""
MANUAL_VIDEO_URL = ""

# Script and css references for dependencies (can be substituted for separate CDN here)
ASMSELECT_CSS = 'static/lib/asmselect/1.0.4a/jquery.asmselect.css'
ASMSELECT_JS = 'static/lib/asmselect/1.0.4a/jquery.asmselect.js'
BASE64_JS = 'static/lib/base64/0.3.0/base64.min.js'
CODEMIRROR_JS = 'static/lib/codemirror/5.11/lib/codemirror.js'
CODEMIRROR_CSS = 'static/lib/codemirror/5.11/lib/codemirror.css'
CODEMIRROR_BASE = 'static/lib/codemirror/5.11/'
EXIFRESTORER_JS = 'static/lib/exifrestorer/1.0.0/exifrestorer.js'
FLOT_JS = 'static/lib/flot/0.8.3/jquery.flot.min.js'
FLOT_PIE_JS = 'static/lib/flot/0.8.3/jquery.flot.pie.min.js'
FULLCALENDAR_CSS = 'static/lib/fullcalendar/3.2.0/fullcalendar.min.css'
FULLCALENDAR_JS = 'static/lib/fullcalendar/3.2.0/fullcalendar.min.js'
JQUERY_UI_CSS = 'static/lib/jqueryui/jquery-ui-themes-1.11.2/themes/%(theme)s/jquery-ui.css'
JQUERY_UI_JS = 'static/lib/jqueryui/jquery-ui-1.11.2/jquery-ui.min.js'
JQUERY_JS = 'static/lib/jquery/2.1.4/jquery.min.js'
JQUERY_MOBILE_CSS = 'static/lib/jquerymobile/1.4.5/jquery.mobile.min.css'
JQUERY_MOBILE_JS = 'static/lib/jquerymobile/1.4.5/jquery.mobile.min.js'
LEAFLET_CSS = 'static/lib/leaflet/1.3.1/leaflet.css'
LEAFLET_JS = 'static/lib/leaflet/1.3.1/leaflet.js'
MOMENT_JS = 'static/lib/moment/2.17.1/moment.min.js'
MOUSETRAP_JS = 'static/lib/mousetrap/1.4.6/mousetrap.min.js'
PATH_JS = 'static/lib/pathjs/0.8.4.smcom/path.min.js'
SIGNATURE_JS = 'static/lib/signature/1.1.1/jquery.signature.min.js'
TABLESORTER_CSS = 'static/lib/tablesorter/2.7.12/themes/theme.asm.css'
TABLESORTER_JS = 'static/lib/tablesorter/2.7.12/jquery.tablesorter.min.js'
TABLESORTER_WIDGETS_JS = 'static/lib/tablesorter/2.7.12/jquery.tablesorter.widgets.min.js'
TIMEPICKER_CSS = 'static/lib/timepicker/0.3.3/jquery.ui.timepicker.css'
TIMEPICKER_JS = 'static/lib/timepicker/0.3.3/jquery.ui.timepicker.js'
TINYMCE_4_JS = 'static/lib/tinymce/4.7.13-asm1/tinymce/js/tinymce/tinymce.min.js'
TOUCHPUNCH_JS = 'static/lib/touchpunch/0.2.3/jquery.ui.touch-punch.min.js'

SMCOM_PAYMENT_LINK = ""
SMCOM_LOGIN_URL = ""
