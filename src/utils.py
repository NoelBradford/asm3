#!/usr/bin/python

import al
import codecs
import configuration
import csv as extcsv
import datetime
import decimal
import hashlib
import htmlentitydefs
import json as extjson
import os
import re
import requests
import smtplib
import subprocess
import sys
import tempfile
import thread
import urllib2
import users
import web
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import make_msgid, formatdate
from email import Charset, Encoders
from i18n import _, display2python, format_currency_no_symbol, format_time, python2display, VERSION
from cStringIO import StringIO
from sitedefs import BASE_URL, SMTP_SERVER, FROM_ADDRESS, HTML_TO_PDF

# Global reference to the Python websession. This is used to allow
# debug mode with webpy by keeping a global single copy of the
# session (in debug mode, module reloading means you'd create two
# session objects)
websession = None

# Global reference to the current code path
PATH = os.path.dirname(os.path.abspath(__file__)) + os.sep

# Regex for counting pages in PDF file data
pdfcountpages = re.compile(r"/Type\s*/Page([^s]|$)", re.MULTILINE | re.DOTALL)

class PostedData(object):
    """
    Helper class for reading fields from the web.py web.input object
    and doing type coercion.
    """
    data = None
    locale = None

    def __init__(self, data, locale):
        self.data = data
        self.locale = locale

    def boolean(self, field):
        if field not in self.data:
            return 0
        if self.data[field] == "checked" or self.data[field] == "on":
            return 1
        else:
            return 0

    def date(self, field):
        """ Returns a date key from a datafield """
        if field in self.data:
            return display2python(self.locale, self.data[field])
        else:
            return None

    def datetime(self, datefield, timefield):
        """ Returns a datetime field """
        if datefield in self.data:
            d = display2python(self.locale, self.data[datefield])
            if d is None: return None
            if timefield in self.data:
                tbits = self.data[timefield].split(":")
                hour = 0
                minute = 0
                second = 0
                if len(tbits) > 0:
                    hour = cint(tbits[0])
                if len(tbits) > 1:
                    minute = cint(tbits[1])
                if len(tbits) > 2:
                    second = cint(tbits[2])
                t = datetime.time(hour, minute, second)
                d = d.combine(d, t)
            return d
        else:
            return None

    def integer(self, field, default=0):
        """ Returns an integer key from a datafield """
        if field in self.data:
            return cint(self.data[field])
        else:
            return default

    def integer_list(self, field):
        """
        Returns a list of integers from a datafield that contains
        comma separated numbers.
        """
        if field in self.data:
            s = self.string(field)
            items = s.split(",")
            ids = []
            for i in items:
                if is_numeric(i):
                    ids.append(cint(i))
            return ids
        else:
            return []

    def floating(self, field, default=0.0):
        """ Returns a float key from a datafield """
        if field in self.data:
            return cfloat(self.data[field])
        else:
            return default

    def string(self, field, strip=True, default=""):
        """ Returns a string key from a datafield """
        if field in self.data:
            s = encode_html(self.data[field])
            if strip: s = s.strip()
            return s
        else:
            return default

    def filename(self, default=""):
        if "filechooser" in self.data:
            return encode_html(self.data.filechooser.filename)
        return default

    def filedata(self, default=""):
        if "filechooser" in self.data:
            return self.data.filechooser.value
        return default

    def __contains__(self, key):
        return key in self.data

    def has_key(self, key):
        return key in self.data

    def __getitem__(self, key):
        return self.string(key)

    def __setitem__(self, key, value):
        self.data[key] = value

    def __repr__(self):
        return json(self.data)

class AdvancedSearchBuilder(object):
    """
    Builds an advanced search (requires a post with multiple supplied parameters)
    as = AdvancedSearchBuilder(dbo, post)
    as.add_id("litterid", "a.AcceptanceNumber")
    as.add_str("rabiestag", "a.RabiesTag")
    as.ands, as.values
    """

    ands = []
    values = []
    dbo = None
    post = None

    def __init__(self, dbo, post):
        self.dbo = dbo
        self.post = post
        self.ands = []
        self.values = []

    def add_id(self, cfield, field): 
        """ Adds a clause for comparing an ID field """
        if self.post[cfield] != "" and self.post.integer(cfield) > -1:
            self.ands.append("%s = ?" % field)
            self.values.append(self.post.integer(cfield))

    def add_id_pair(self, cfield, field, field2): 
        """ Adds a clause for a posted value to one of two ID fields (eg: breeds) """
        if self.post[cfield] != "" and self.post.integer(cfield) > 0: 
            self.ands.append("(%s = ? OR %s = ?)" % (field, field2))
            self.values.append(self.post.integer(cfield))
            self.values.append(self.post.integer(cfield))

    def add_str(self, cfield, field): 
        """ Adds a clause for a posted value to a string field """
        if self.post[cfield] != "":
            x = self.post[cfield].lower().replace("'", "`")
            x = "%%%s%%" % x
            self.ands.append("(LOWER(%s) LIKE ? OR LOWER(%s) LIKE ?)" % (field, field))
            self.values.append(x)
            self.values.append(decode_html(x))

    def add_str_pair(self, cfield, field, field2): 
        """ Adds a clause for a posted value to one of two string fields """
        if self.post[cfield] != "":
            x = "%%%s%%" % self.post[cfield].lower()
            self.ands.append("(LOWER(%s) LIKE ? OR LOWER(%s) LIKE ?)" % (field, field2))
            self.values.append(x)
            self.values.append(x)

    def add_str_triplet(self, cfield, field, field2, field3): 
        """ Adds a clause for a posted value to one of three string fields """
        if self.post[cfield] != "":
            x = "%%%s%%" % self.post[cfield].lower()
            self.ands.append("(LOWER(%s) LIKE ? OR LOWER(%s) LIKE ? OR LOWER(%s) LIKE ?)" % (field, field2, field3))
            self.values.append(x)
            self.values.append(x)
            self.values.append(x)

    def add_date(self, cfieldfrom, cfieldto, field): 
        """ Adds a clause for a posted date range to a date field """
        if self.post[cfieldfrom] != "" and self.post[cfieldto] != "":
            self.post.data["dayend"] = "23:59:59"
            self.ands.append("%s >= ? AND %s <= ?" % (field, field))
            self.values.append(self.post.date(cfieldfrom))
            self.values.append(self.post.datetime(cfieldto, "dayend"))

    def add_filter(self, f, condition):
        """ Adds a complete clause if posted filter value is present """
        if self.post["filter"].find(f) != -1: self.ands.append(condition)

    def add_comp(self, cfield, value, condition):
        """ Adds a clause if a field holds a value """
        if self.post[cfield] == value: self.ands.append(condition)

    def add_words(self, cfield, field):
        """ Adds a separate clause for each word in cfield """
        if self.post[cfield] != "":
            words = self.post[cfield].split(" ")
            for w in words:
                x = w.lower().replace("'", "`")
                x = "%%%s%%" % x
                self.ands.append("(LOWER(%s) LIKE ? OR LOWER(%s) LIKE ?)" % (field, field))
                self.values.append(x)
                self.values.append(decode_html(x))

class SimpleSearchBuilder(object):
    """
    Builds a simple search (based on a single search term)
    ss = SimpleSearchBuilder(dbo, "test")
    ss.add_field("a.AnimalName")
    ss.add_field("a.ShelterCode")
    ss.add_fields([ "a.BreedName", "a.AnimalComments" ])
    ss.ors, ss.values
    """
    
    q = ""
    qlike = ""
    ors = []
    values = []
    dbo = None

    def __init__(self, dbo, q):
        self.dbo = dbo
        self.q = q.replace("'", "`")
        self.qlike = "%%%s%%" % self.q.lower()
        self.ors = []
        self.values = []

    def add_field(self, field):
        """ Add a field to search """
        self.ors.append("(LOWER(%s) LIKE ? OR LOWER(%s) LIKE ?)" % (field, field))
        self.values.append(self.qlike)
        self.values.append(decode_html(self.qlike))

    def add_field_value(self, field, value):
        """ Add a field with a specific value """
        self.ors.append("%s = ?" % field)
        self.values.append(value)

    def add_fields(self, fieldlist):
        """ Add clauses for many fields in one list """
        for f in fieldlist:
            self.add_field(f)

    def add_large_text_fields(self, fieldlist):
        """ Add clauses for many large text fields (only search in smaller databases) in one list """
        if not self.dbo.is_large_db:
            for f in fieldlist:
                self.add_field(f)

    def add_words(self, field):
        """ Adds each word in the term as and clauses so that each word is separately matched and has to be present """
        ands = []
        for w in self.q.split(" "):
            x = w.lower().replace("'", "`")
            x = "%%%s%%" % x
            ands.append("(LOWER(%s) LIKE ? OR LOWER(%s) LIKE ?)" % (field, field))
            self.values.append(x)
            self.values.append(decode_html(x))
        self.ors.append("(" + " AND ".join(ands) + ")")

    def add_clause(self, clause):
        self.ors.append(clause)
        self.values.append(self.qlike)

def is_currency(f):
    """ Returns true if the field with name f is a currency field """
    CURRENCY_FIELDS = "AMT AMOUNT DONATION DAILYBOARDINGCOST COSTAMOUNT COST FEE LICENCEFEE DEPOSITAMOUNT FINEAMOUNT UNITPRICE VATAMOUNT"
    return f.upper().startswith("MONEY") or CURRENCY_FIELDS.find(f.upper()) != -1

def is_date(d):
    """ Returns true if d is a date field """
    return isinstance(d, datetime.datetime) or isinstance(d, datetime.date)

def is_numeric(s):
    """
    Returns true if the string s is a number
    """
    try:
        float(s)
    except ValueError:
        return False
    else:
        return True

def is_str(s):
    """
    Returns true if the string s is a str
    """
    return isinstance(s, str)

def is_unicode(s):
    """
    Returns true if the string s is unicode
    """
    return isinstance(s, unicode) # noqa: F821

def cunicode(s, encoding = "utf8"):
    """
    Converts a str to unicode
    """
    return unicode(s, encoding) # noqa: F821

def atoi(s):
    """
    Converts only the numeric portion of a string to an integer
    """
    x = re.findall('\d+', s)
    if x is None or len(x) == 0: return 0
    return cint(x[0])

def cint(s):
    """
    Converts a string to an int, coping with None and non-int values
    """
    try:
        return int(s)
    except:
        return 0

def cfloat(s):
    """
    Converts a string to a float, coping with None and non-numeric values
    """
    try:
        return float(s)
    except:
        return float(0)

def cmd(c, shell=False):
    """
    Runs the command c and returns a tuple of return code and output
    """
    output = None
    try:
        output = subprocess.check_output(c.split(" "), stderr=subprocess.STDOUT, shell=shell)
        return (0, output)
    except subprocess.CalledProcessError as e:
        return (e.returncode, e.output)

def file_contains(f, v):
    """
    Returns true if file f contains value v
    """
    return 0 == os.system("grep %s %s" % (v, f))

def iif(c, t, f):
    """
    Evaluates c and returns t for True or f for False
    """
    return c and t or f

def nulltostr(s):
    try:
        if s is None: return ""
        if is_unicode(s):
            s = s.encode("ascii", "xmlcharrefreplace")
        return str(s)
    except:
        em = "[" + str(sys.exc_info()[0]) + "]"
        return em

def filename_only(filename):
    """ If a filename has a path, return just the name """
    if filename.find("/") != -1: filename = filename[filename.rfind("/")+1:]
    if filename.find("\\") != -1: filename = filename[filename.rfind("\\")+1:]
    return filename

def json_parse(s):
    """
    Parses json and returns an object tree
    """
    return extjson.loads(s)

def json_handler(obj):
    """
    Used to help when serializing python objects to json
    """
    if obj is None:
        return "null"
    elif hasattr(obj, "isoformat"):
        return obj.isoformat()
    elif type(obj) == datetime.timedelta:
        hours, remain = divmod(obj.seconds, 3600)
        minutes, seconds = divmod(remain, 60)
        return "%02d:%02d:%02d" % (hours, minutes, seconds)
    elif isinstance(obj, decimal.Decimal):
        return str(obj)
    elif isinstance(obj, type):
        return str(obj)
    else:
        raise TypeError('Object of type %s with value of %s is not JSON serializable' % (type(obj), repr(obj)))

def json(obj, readable = False):
    """
    Takes a python object and serializes it to JSON.
    None objects are turned into "null"
    datetime objects are turned into string isoformat for use with js Date.
    This function switches </ for <\/ in output to prevent HTML tags in any content
        from breaking out of a script tag.
    readable: If True, line breaks and padding are added to make it human-readable
    """
    if not readable:
        return extjson.dumps(obj, default=json_handler).replace("</", "<\\/")
    else:
        return extjson.dumps(obj, default=json_handler, indent=4, separators=(',', ': ')).replace("</", "<\\/")

def address_first_line(address):
    """
    Returns the first line of an address
    """
    if address is None: return ""
    bits = address.split("\n")
    if len(bits) > 0:
        return bits[0]
    return ""

def address_house_number(address):
    """
    Returns the house number from an address
    """
    fl = address_first_line(address)
    if fl == "": return ""
    bits = fl.split(" ")
    if is_numeric(bits[0]):
        return bits[0]
    return ""

def address_street_name(address):
    """
    Returns the street name from an address line
    """
    fl = address_first_line(address)
    if fl == "": return ""
    bits = fl.split(" ", 1)
    if len(bits) == 2:
        return bits[1]
    return ""

def spaceleft(s, spaces):
    """
    leftpads a string to a number of spaces
    """
    sp = "                                                 "
    if len(s) > spaces: return s
    nr = spaces - len(s)
    return sp[0:nr] + s

def spaceright(s, spaces):
    """
    rightpads a string to a number of spaces
    """
    sp = "                                                 "
    if len(s) > spaces: return s
    nr = spaces - len(s)
    return s + sp[0:nr]

def padleft(num, digits):
    """
    leftpads a number to digits
    """
    zeroes = "000000000000000"
    s = str(num)
    if len(s) > digits: return s
    nr = digits - len(s)
    return zeroes[0:nr] + s

def padright(num, digits):
    """
    rightpads a number to digits
    """
    zeroes = "000000000000000"
    s = str(num)
    if len(s) > digits: return s
    nr = digits - len(s)
    return s + zeroes[0:nr]

def truncate(s, length = 100):
    """
    Truncates a string to length. If the string is longer than
    length, appends ...
    Removes any unicode sequences
    HTML entities count as one character
    """
    if s is None: s = ""
    s = strip_html_tags(s)
    s = strip_non_ascii(s)
    if len(decode_html(s)) < length: return s
    return substring(s, 0, length) + "..."

def substring(s, start, end = None):
    """
    Returns a substring. If s contains any HTML/unicode escape sequences, they
    are evaluated and count as one char.
    """
    us = decode_html(s)
    if end is None or end > len(us):
        ur = us[start:]
    else:
        ur = us[start:end]
    return ur.encode("ascii", "xmlcharrefreplace")

def strip_html_tags(s):
    """
    Removes all html tags from a string, leaving just the
    content behind.
    """
    return re.sub('<.*?>', '', s)

def strip_non_ascii(s):
    """
    Remove any non-ascii characters from a string str
    """
    return "".join(i for i in s if ord(i)<128)

def decode_html(s):
    """
    Decodes HTML entities and returns a unicode string.
    """
    def to_char(p):
        return unichr(p) # noqa: F821
    # It's empty, return an empty string
    if s is None: return ""
    # It's not a string, we can't deal with this
    if not is_str(s): return s
    matches = re.findall("&#\d+;", s)
    if len(matches) > 0:
        hits = set(matches)
        for hit in hits:
            name = hit[2:-1]
            try:
                entnum = int(name)
                s = s.replace(hit, to_char(entnum))
            except ValueError:
                pass
    matches = re.findall("&#[xX][0-9a-fA-F]+;", s)
    if len(matches) > 0:
        hits = set(matches)
        for hit in hits:
            hexv = hit[3:-1]
            try:
                entnum = int(hexv, 16)
                s = s.replace(hit, to_char(entnum))
            except ValueError:
                pass
    matches = re.findall("&\w+;", s)
    hits = set(matches)
    amp = "&amp;"
    if amp in hits:
        hits.remove(amp)
    for hit in hits:
        name = hit[1:-1]
        if name in htmlentitydefs.name2codepoint:
            s = s.replace(hit, to_char(htmlentitydefs.name2codepoint[name]))
    s = s.replace(amp, "&")
    return s

def encode_html(s):
    """
    Encodes Unicode strings as HTML entities in an ASCII string
    """
    if s is None: return ""
    if is_str(s):
        return cunicode(s).encode("ascii", "xmlcharrefreplace")
    else:
        return s.encode("ascii", "xmlcharrefreplace")

def html_to_uri(s):
    """
    Converts HTML escaped entities to URI escaping.
    &#256; -> %ff%01
    """
    for ent in re.findall("&#(\d+?);", s):
        h = "%04x" % cint(ent)
        s = s.replace("&#" + ent + ";", "%" + h[0:2] + "%" + h[2:4])
    return s

def list_overlap(l1, l2):
    """
    Returns True if any of the items in l1 are present in l2.
    """
    for l in l1:
        if l in l2:
            return True
    return False

def regex_multi(pattern, findin):
    """
    Returns all matches for pattern in findin
    """
    return re.findall(pattern, findin)

def regex_one(pattern, findin):
    """
    Returns the first match for pattern in findin or an empty
    string for no match.
    """
    r = regex_multi(pattern, findin)
    if len(r) == 0: return ""
    return r[0]

class ASMValidationError(web.HTTPError):
    """
    Custom error thrown by data modules when validation fails
    """
    msg = ""
    def __init__(self, msg):
        self.msg = msg
        status = '500 Internal Server Error'
        headers = { 'Content-Type': "text/html" }
        data = "<h1>Validation Error</h1><p>%s</p>" % msg
        if "headers" not in web.ctx: web.ctx.headers = []
        web.HTTPError.__init__(self, status, headers, data)

    def getMsg(self):
        return self.msg

class ASMPermissionError(web.HTTPError):
    """
    Custom error thrown by data modules when permission checks fail
    """
    def __init__(self, msg):
        status = '500 Internal Server Error'
        headers = { 'Content-Type': "text/html" }
        data = "<h1>Permission Error</h1><p>%s</p>" % msg
        if "headers" not in web.ctx: web.ctx.headers = []
        web.HTTPError.__init__(self, status, headers, data)

class ASMError(web.HTTPError):
    """
    Custom error thrown by data modules 
    """
    def __init__(self, msg):
        status = '500 Internal Server Error'
        headers = { 'Content-Type': "text/html" }
        data = "<h1>Error</h1><p>%s</p>" % msg
        if "headers" not in web.ctx: web.ctx.headers = []
        web.HTTPError.__init__(self, status, headers, data)

def escape_tinymce(content):
    """
    Escapes HTML content for placing inside a tinymce
    textarea. Basically, just the < and > markers - other
    escaped tokens should be left for the browser to
    expand - except &gt; and &lt; for our << >> markers
    (god this is confusing), which need to be double
    escaped or tinymce breaks. 
    """
    c = strip_non_ascii(content)
    c = c.replace("&gt;", "&amp;gt;")
    c = c.replace("&lt;", "&amp;lt;")
    c = c.replace("<", "&lt;")
    c = c.replace(">", "&gt;")
    return c

class UnicodeCSVReader(object):
    """
    A CSV reader that reads UTF-8 and converts any unicode values to
    XML entities.
    """
    encoding = "utf-8-sig"
    def __init__(self, f, dialect=extcsv.excel, encoding="utf-8-sig", **kwds):
        self.encoding = encoding
        self.reader = extcsv.reader(f, dialect=dialect, **kwds)

    def next(self):
        """ 
        next() -> unicode
        This function reads and returns the next line as a Unicode string.
        """
        row = self.reader.next()
        return [ self.process(s) for s in row ]

    def process(self, s):
        """ Process an element """
        x = cunicode(s, self.encoding) # decode to unicode with selected encoding
        x = x.encode("ascii", "xmlcharrefreplace") # encode back to ascii, using XML entities
        if x.startswith("\""): x = x[1:] # strip any unwanted quotes from the beginning
        if x.endswith("\""): x = x[0:len(x)-1] # ... and end
        return x

    def __iter__(self):
        return self

class UnicodeCSVDictReader(object):
    """
    A CSV reader that uses UnicodeCSVReader to handle UTF-8 and returns
    each row as a dictionary instead.
    """
    def __init__(self, f):
        self.reader = UnicodeCSVReader(f)
        self.cols = self.reader.next()

    def next(self):
        row = self.reader.next()
        d = {}
        for (c, r) in zip(self.cols, row):
            d[c] = r
        return d

    def __iter__(self):
        return self

class UnicodeCSVWriter(object):
    """
    A CSV writer which will write rows to CSV file "f",
    which is encoded in the given encoding.
    """
    def __init__(self, f, dialect=extcsv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.queue = StringIO()
        self.writer = extcsv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        outbuf = []
        for s in row:
            if is_unicode(s):
                outbuf.append(s.encode("utf-8"))
            else:
                outbuf.append(s)
        self.writer.writerow(outbuf)
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # write to the target stream
        self.stream.write(data)
        # empty queue
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)

def csv(l, rows, cols = None, includeheader = True):
    """
    Creates a CSV file from a set of resultset rows. If cols has been 
    supplied as a list of strings, fields will be output in that
    order.
    """
    if rows is None or len(rows) == 0: return ""
    strio = StringIO()
    out = UnicodeCSVWriter(strio)
    if cols is None:
        cols = []
        for k, v in rows[0].iteritems():
            cols.append(k)
        cols = sorted(cols)
    if includeheader: 
        out.writerow(cols)
    for r in rows:
        rd = []
        for c in cols:
            if is_currency(c):
                rd.append(decode_html(format_currency_no_symbol(l, r[c])))
            elif is_date(r[c]):
                timeportion = "00:00:00"
                dateportion = ""
                try:
                    dateportion = python2display(l, r[c])
                    timeportion = format_time(r[c])
                except:
                    pass # Don't stop the show for bad dates/times
                if timeportion != "00:00:00": # include time if non-midnight
                    dateportion = "%s %s" % (dateportion, timeportion)
                rd.append(decode_html(dateportion))
            else:
                rd.append(decode_html(r[c]))
        out.writerow(rd)
    return strio.getvalue()

def fix_relative_document_uris(s, baseurl, account = "" ):
    """
    Switches the relative uris used in document templates for absolute
    ones to the service so that documents will work outside of 
    the ASM UI.
    """
    patterns = (
        # animal images
        ( "image?mode=animal&amp;id=", "animal_image", "animalid" ),
        ( "image?db={account}&ampmode=animal&amp;id=", "animal_image", "animalid" ),
        ( "image?db={account}&mode=animal&id=", "animal_image", "animalid" ),
        ( "image?db={account}&amp;mode=nopic", "extra_image", "title=nopic.jpg&xx" ),

        # animal thumbnail images
        ( "image?mode=animalthumb&amp;id=", "animal_thumbnail", "animalid" ),
        ( "image?db={account}&amp;mode=animalthumb&amp;id=", "animal_thumbnail", "animalid" ),
        ( "image?db={account}&mode=animalthumb&id=", "animal_thumbnail", "animalid" ),

        # report/extra images
        ( "image?mode=dbfs&amp;id=/reports/", "extra_image", "title" ),
        ( "image?db={account}&amp;mode=dbfs&amp;id=/reports/", "extra_image", "title" ),

        # any image in the dbfs by path
        ( "image?mode=dbfs&amp;id=", "dbfs_image", "title" ),
        ( "image?db={account}&amp;mode=dbfs&amp;id=", "dbfs_image", "title" )
    )
    for f, m, p in patterns:
        f = f.replace("{account}", account)
        s = s.replace(f, baseurl + "/service?method=" + m + "&account=" + account + "&" + p + "=")
    return s

def substitute_tags(searchin, tags, use_xml_escaping = True, opener = "&lt;&lt;", closer = "&gt;&gt;"):
    """
    Substitutes the dictionary of tags in "tags" for any found
    in "searchin". opener and closer denote the start of a tag,
    if use_xml_escaping is set to true, then tags are XML escaped when
    output and opener/closer are escaped.
    """
    if not use_xml_escaping:
        opener = opener.replace("&lt;", "<").replace("&gt;", ">")
        closer = closer.replace("&lt;", "<").replace("&gt;", ">")

    s = searchin
    sp = s.find(opener)
    while sp != -1:
        ep = s.find(closer, sp + len(opener))
        if ep != -1:
            matchtag = s[sp + len(opener):ep].upper()
            newval = ""
            if matchtag in tags:
                newval = tags[matchtag]
                if newval is not None:
                    newval = str(newval)
                    if use_xml_escaping and not newval.lower().startswith("<img"):
                        newval = newval.replace("&", "&amp;")
                        newval = newval.replace("<", "&lt;")
                        newval = newval.replace(">", "&gt;")
            s = s[0:sp] + str(newval) + s[ep + len(closer):]
            sp = s.find(opener, sp)
        else:
            # No end marker for this tag, stop processing
            break
    return s

def check_locked_db(session):
    if session.dbo and session.dbo.locked: 
        l = session.locale
        raise ASMPermissionError(_("This database is locked.", l))

def check_loggedin(session, web, loginpage = "login"):
    """
    Checks if we have a logged in user and if not, redirects to
    the login page
    """
    if not is_loggedin(session):
        path = web.ctx.path
        if path.startswith("/"): path = path[1:]
        query = str(web.ctx.query)
        raise web.seeother("%s/%s?target=%s%s" % (BASE_URL, loginpage, path, query))
    else:
        # update the last user activity
        users.update_user_activity(session.dbo, session.user)

def is_loggedin(session):
    """
    Returns true if the user is logged in
    """
    return "user" in session and session.user is not None

def md5_hash(s):
    """
    Returns an md5 hash of a string
    """
    m = hashlib.md5()
    m.update(s)
    s = m.hexdigest()
    return s

def get_url(url, headers = {}, cookies = {}, timeout = None):
    """
    Retrieves a URL
    """
    # requests timeout is seconds/float, but some may call this with integer ms instead so convert
    if timeout is not None and timeout > 1000: timeout = timeout / 1000.0
    r = requests.get(url, headers = headers, cookies=cookies, timeout=timeout)
    return { "cookies": r.cookies, "headers": r.headers, "response": r.text, "status": r.status_code, "requestheaders": r.request.headers, "requestbody": r.request.body }

def get_image_url(url, headers = {}, cookies = {}, timeout = None):
    """
    Retrives an image from a URL
    """
    # requests timeout is seconds/float, but some may call this with integer ms instead so convert
    if timeout is not None and timeout > 1000: timeout = timeout / 1000.0
    r = requests.get(url, headers = headers, cookies=cookies, timeout=timeout, stream=True)
    s = StringIO()
    for chunk in r:
        s.write(chunk) # default from requests is 128 byte chunks
    return { "cookies": r.cookies, "headers": r.headers, "response": s.getvalue(), "status": r.status_code, "requestheaders": r.request.headers, "requestbody": r.request.body }

def post_data(url, data, contenttype = "", httpmethod = "", headers = {}):
    """
    Posts data to a URL as the body
    httpmethod: POST by default
    """
    try:
        if contenttype != "": headers["Content-Type"] = contenttype
        req = urllib2.Request(url, data, headers)
        if httpmethod != "": req.get_method = lambda: httpmethod
        resp = urllib2.urlopen(req)
        return { "requestheaders": headers, "requestbody": data, "headers": resp.info().headers, "response": resp.read(), "status": resp.getcode() }
    except urllib2.HTTPError as e:
        return { "requestheaders": headers, "requestbody": data, "headers": e.info().headers, "response": e.read(), "status": e.getcode() }

def post_form(url, fields, headers = {}, cookies = {}):
    """
    Does a form post
    url: The http url to post to
    fields: A map of { name: value } elements
    headers: A map of { name: value } headers
    return value is the http headers (a map) and server's response as a string
    """
    r = requests.post(url, data=fields, headers=headers, cookies=cookies)
    return { "cookies": r.cookies, "headers": r.headers, "response": r.text, "status": r.status_code, "requestheaders": r.request.headers, "requestbody": r.request.body }

def post_multipart(url, fields = None, files = None, headers = {}, cookies = {}):
    """
    Does a multipart form post
    url: The http url to post to
    files: A map of { name: (name, data, mime) }
    fields: A map of { name: value } elements
    headers: A map of { name: value } headers
    return value is the http headers (a map) and server's response as a string
    """
    r = requests.post(url, files=files, data=fields, headers=headers, cookies=cookies)
    return { 
        "cookies": r.cookies, 
        "headers": r.headers, 
        "response": r.text, 
        "status": r.status_code, 
        "redirects": len(r.history), 
        "requestheaders": r.request.headers, 
        "requestbody": r.request.body 
    }

def post_json(url, json, headers = {}):
    """
    Posts a JSON document to a URL
    """
    return post_data(url, json, contenttype="application/json", headers=headers)

def patch_json(url, json, headers = {}):
    """
    Posts a JSON document to a URL with the PATCH HTTP method
    """
    return post_data(url, json, contenttype="application/json", httpmethod="PATCH", headers=headers)

def post_xml(url, xml, headers = {}):
    """
    Posts an XML document to a URL
    """
    return post_data(url, xml, contenttype="text/xml", headers=headers)

def read_text_file(name):
    """
    Reads a text file and returns the result as a string.
    """
    with codecs.open(name, 'r', encoding='utf8') as f:
        text = f.read()
    return text.encode("ascii", "xmlcharrefreplace")

def read_binary_file(name):
    """
    Reads a binary file and returns the result
    """
    with open(name, "rb") as f:
        return f.read()

def write_binary_file(name, data):
    """
    Writes a binary file
    """
    with open(name, "wb") as f:
        f.write(data)

def html_email_to_plain(s):
    """
    Turns an HTML email into plain text by converting
    paragraph closers, br tags and rows into line breaks, then
    removing the tags.
    """
    s = s.replace("</p>", "\n</p>")
    s = s.replace("<br", "\n<br")
    s = s.replace("</tr>", "\n</tr>")
    s = strip_html_tags(s)
    return s

def send_email(dbo, replyadd, toadd, ccadd = "", bccadd = "", subject = "", body = "", contenttype = "plain", attachmentdata = None, attachmentfname = "", exceptions = True):
    """
    Sends an email.
    fromadd is a single email address
    toadd is a comma/semi-colon separated list of email addresses 
    ccadd is a comma/semi-colon separated list of email addresses
    bccadd is a comma/semi-colon separated list of email addresses
    subject, body are strings
    contenttype is either "plain" or "html"
    attachmentdata: If an attachment should be added, the unencoded data
    attachmentfname: If an attachment should be added, the file name to give it
    exceptions: If True, throws exceptions due to sending problems
    returns True on success

    For HTML emails, a plaintext part is converted and added. If the HTML
    does not have html/body tags, they are also added.
    """
    def parse_email(s):
        # Returns a tuple of description and address
        s = s.strip()
        fp = s.find("<")
        ep = s.find(">")
        description = s
        address = s
        if fp != -1 and ep != -1:
            description = s[0:fp].strip()
            address = s[fp+1:ep].strip()
        return (description, address)

    def strip_email(s):
        # Just returns the address portion of an email
        description, address = parse_email(s)
        return address

    def add_header(msg, header, value):
        """
        Adds a header to the message, expands any HTML entities
        and re-encodes as utf-8 before adding to the message if necessary.
        If the message doesn't contain HTML entities, then it is just
        added normally as 7-bit ascii
        """
        value = value.replace("\n", "") # line breaks are not allowed in headers
        if value.find("&#") != -1:
            # Is this an address field? If so, parse the addresses and 
            # encode the descriptions
            if header in ("To", "From", "Cc", "Bcc", "Bounces-To", "Reply-To"):
                addresses = value.split(",")
                newval = ""
                for a in addresses:
                    description, address = parse_email(a)
                    if newval != "": newval += ", "
                    newval += "\"%s\" <%s>" % (Header(decode_html(description).encode("utf-8"), "utf-8"), address)
                msg[header] = newval
            else:
                h = Header(decode_html(value).encode("utf-8"), "utf-8")
                msg[header] = h
        else:
            msg[header] = value

    # If the email is plain text, but contains HTML escape characters, 
    # switch it to being an html message instead and make sure line 
    # breaks are retained
    if body.find("&#") != -1 and contenttype == "plain":
        contenttype = "html"
        body = body.replace("\n", "<br />")
        Charset.add_charset("utf-8", Charset.QP, Charset.QP, "utf-8")

    # If the message is HTML, but does not contain an HTML tag, assume it's
    # a document fragment and wrap it (this lowers spamassassin scores)
    if body.find("<html") == -1 and contenttype == "html":
        body = "<!DOCTYPE html>\n<html>\n<body>\n%s</body></html>" % body

    # Build the from address from our sitedef
    fromadd = FROM_ADDRESS
    fromadd = fromadd.replace("{organisation}", configuration.organisation(dbo))
    fromadd = fromadd.replace("{alias}", dbo.alias)
    fromadd = fromadd.replace("{database}", dbo.database)

    # Check for any problems in the reply address, such as unclosed address
    if replyadd.find("<") != -1 and replyadd.find(">") == -1:
        replyadd += ">"

    # Construct the mime message
    msg = MIMEMultipart("mixed")
    add_header(msg, "Message-ID", make_msgid())
    add_header(msg, "Date", formatdate())
    add_header(msg, "X-Mailer", "Animal Shelter Manager %s" % VERSION)
    subject = truncate(subject, 69) # limit subject to 78 chars - "Subject: "
    add_header(msg, "Subject", subject)
    add_header(msg, "From", fromadd)
    add_header(msg, "Reply-To", replyadd)
    add_header(msg, "Bounces-To", replyadd)
    add_header(msg, "To", toadd)
    if ccadd != "": add_header(msg, "Cc", ccadd)

    # Create an alternative part with plain text and html messages
    msgbody = MIMEMultipart("alternative")

    # Attach the plaintext portion (html_email_to_plain on an already plaintext
    # email does nothing).
    msgbody.attach(MIMEText(html_email_to_plain(body), "plain"))

    # Attach the HTML portion if this is an HTML message
    if contenttype == "html":
        msgbody.attach(MIMEText(body, "html"))
    
    # Add the message text
    msg.attach(msgbody)

    # If a file attachment has been specified, add it to the message
    if attachmentdata is not None:
        part = MIMEBase('application', "octet-stream")
        part.set_payload( attachmentdata )
        Encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="%s"' % attachmentfname)
        msg.attach(part)
 
    # Construct the list of to addresses. We strip email addresses so
    # only the you@domain.com portion remains for us to pass to the
    # SMTP server. 
    tolist = [strip_email(x) for x in toadd.split(",")]
    if ccadd != "":  tolist += [strip_email(x) for x in ccadd.split(",")]
    if bccadd != "": tolist += [strip_email(x) for x in bccadd.split(",")]

    replyadd = strip_email(replyadd)

    al.debug("from: %s, reply-to: %s, to: %s, subject: %s, body: %s" % \
        (fromadd, replyadd, str(tolist), subject, body), "utils.send_email", dbo)
    
    # Load the server config over default vars
    sendmail = True
    host = ""
    port = 25
    username = ""
    password = ""
    usetls = False
    if SMTP_SERVER is not None:
        if "sendmail" in SMTP_SERVER: sendmail = SMTP_SERVER["sendmail"]
        if "host" in SMTP_SERVER: host = SMTP_SERVER["host"]
        if "port" in SMTP_SERVER: port = SMTP_SERVER["port"]
        if "username" in SMTP_SERVER: username = SMTP_SERVER["username"]
        if "password" in SMTP_SERVER: password = SMTP_SERVER["password"]
        if "usetls" in SMTP_SERVER: usetls = SMTP_SERVER["usetls"]
        if "headers" in SMTP_SERVER: 
            for k, v in SMTP_SERVER["headers"].iteritems():
                add_header(msg, k, v)
     
    # Use sendmail or SMTP for the transport depending on config
    if sendmail:
        try:
            if bccadd != "": 
                # sendmail -t processes and removes Bcc header, where SMTP has all recipients (including Bcc) in tolist
                add_header(msg, "Bcc", bccadd) 
            p = subprocess.Popen(["/usr/sbin/sendmail", "-t", "-oi"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdoutdata, stderrdata = p.communicate(msg.as_string())
            if p.returncode != 0: raise Exception("%s %s" % (stdoutdata, stderrdata))
        except Exception as err:
            al.error("sendmail: %s" % str(err), "utils.send_email", dbo)
            if exceptions: raise ASMError(str(err))
    else:
        try:
            smtp = smtplib.SMTP(host, port)
            if usetls:
                smtp.starttls()
            if password.strip() != "":
                smtp.login(username, password)
            smtp.sendmail(fromadd, tolist, msg.as_string())
        except Exception as err:
            al.error("smtp: %s" % str(err), "utils.send_email", dbo)
            if exceptions: raise ASMError(str(err))

def send_bulk_email(dbo, fromadd, subject, body, rows, contenttype):
    """
    Sends a set of bulk emails asynchronously.
    fromadd is an RFC821 address
    subject and body are strings. Either can contain <<TAGS>>
    rows is a list of dictionaries of tag tokens with real values to substitute
    contenttype is either "plain" or "html"
    """
    def do_send():
        for r in rows:
            ssubject = substitute_tags(subject, r, False, opener = "<<", closer = ">>")
            sbody = substitute_tags(body, r)
            toadd = r["EMAILADDRESS"]
            if toadd is None or toadd.strip() == "": continue
            al.debug("sending bulk email: to=%s, subject=%s" % (toadd, ssubject), "utils.send_bulk_email", dbo)
            send_email(dbo, fromadd, toadd, "", "", ssubject, sbody, contenttype, exceptions=False)
    thread.start_new_thread(do_send, ())

def send_user_email(dbo, sendinguser, user, subject, body):
    """
    Sends an email to users.
    sendinguser: The username of the person sending the email (we will look up their email)
    user:        can be an individual username, a rolename or the translated 
                 version of (all) or (everyone) to denote all users.
    """
    DEFAULT_EMAIL = "noreply@sheltermanager.com"
    sendinguser = users.get_users(dbo, sendinguser)
    if len(sendinguser) == 0:
        fromadd = DEFAULT_EMAIL
    else:
        fromadd = sendinguser[0]["EMAILADDRESS"]
        if fromadd is None or fromadd.strip() == "":
            fromadd = DEFAULT_EMAIL
    al.debug("from: %s (%s), to: %s" % (sendinguser, fromadd, user), "utils.send_user_email", dbo)
    allusers = users.get_users(dbo)
    for u in allusers:
        # skip if we have no email address - we can't send it.
        if u["EMAILADDRESS"] is None or u["EMAILADDRESS"].strip() == "": continue
        if user == "*":
            send_email(dbo, fromadd, u["EMAILADDRESS"], "", "", subject, body, exceptions=False)
        elif u["USERNAME"] == user:
            send_email(dbo, fromadd, u["EMAILADDRESS"], "", "", subject, body, exceptions=False)
        elif nulltostr(u["ROLES"]).find(user) != -1:
            send_email(dbo, fromadd, u["EMAILADDRESS"], "", "", subject, body, exceptions=False)

def pdf_count_pages(filedata):
    """
    Given a PDF in filedata, returns the number of pages.
    """
    return len(pdfcountpages.findall(filedata))

def html_to_pdf(htmldata, baseurl = "", account = ""):
    """
    Converts HTML content to PDF and returns the PDF file data.
    """
    # Allow orientation and papersize to be set
    # with directives in the document source - eg: <!-- pdf orientation landscape, pdf papersize letter -->
    orientation = "portrait"
    # Sort out page size arguments
    papersize = "--page-size a4"
    if htmldata.find("pdf orientation landscape") != -1: orientation = "landscape"
    if htmldata.find("pdf orientation portrait") != -1: orientation = "portrait"
    if htmldata.find("pdf papersize a5") != -1: papersize = "--page-size a5"
    if htmldata.find("pdf papersize a4") != -1: papersize = "--page-size a4"
    if htmldata.find("pdf papersize a3") != -1: papersize = "--page-size a3"
    if htmldata.find("pdf papersize letter") != -1: papersize = "--page-size letter"
    # Eg: <!-- pdf papersize exact 52mmx86mm end -->
    ps = regex_one("pdf papersize exact (.+?) end", htmldata) 
    if ps != "":
        w, h = ps.split("x")
        papersize = "--page-width %s --page-height %s" % (w, h)
    # Zoom - eg: <!-- pdf zoom 0.5 end -->
    zoom = "--enable-smart-shrinking"
    zm = regex_one("pdf zoom (.+?) end", htmldata)
    if zm != "":
        zoom = "--disable-smart-shrinking --zoom %s" % zm
    # Margins, top/bottom/left/right eg: <!-- pdf margins 2cm 2cm 2cm 2cm end -->
    margins = "--margin-top 1cm"
    mg = regex_one("pdf margins (.+?) end", htmldata)
    if mg != "":
        tm, bm, lm, rm = mg.split(" ")
        margins = "--margin-top %s --margin-bottom %s --margin-left %s --margin-right %s" % (tm, bm, lm, rm)
    header = "<!DOCTYPE HTML>\n<html>\n<head>"
    header += '<meta http-equiv="content-type" content="text/html; charset=utf-8">\n'
    header += "</head><body>"
    footer = "</body></html>"
    htmldata = htmldata.replace("font-size: xx-small", "font-size: 6pt")
    htmldata = htmldata.replace("font-size: x-small", "font-size: 8pt")
    htmldata = htmldata.replace("font-size: small", "font-size: 10pt")
    htmldata = htmldata.replace("font-size: medium", "font-size: 14pt")
    htmldata = htmldata.replace("font-size: large", "font-size: 18pt")
    htmldata = htmldata.replace("font-size: x-large", "font-size: 24pt")
    htmldata = htmldata.replace("font-size: xx-large", "font-size: 36pt")
    htmldata = fix_relative_document_uris(htmldata, baseurl, account)
    # Remove any img tags with signature:placeholder/user as the src
    htmldata = re.sub('<img.*?signature\:.*?\/>', '', htmldata)
    # Fix up any google QR codes where a protocol-less URI has been used
    htmldata = htmldata.replace("\"//chart.googleapis.com", "\"http://chart.googleapis.com")
    # Use temp files
    inputfile = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
    outputfile = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    inputfile.write(header + htmldata + footer)
    inputfile.flush()
    inputfile.close()
    outputfile.close()
    cmdline = HTML_TO_PDF % { "output": outputfile.name, "input": inputfile.name, "orientation": orientation, "papersize": papersize, "zoom": zoom, "margins": margins }
    code, output = cmd(cmdline)
    if code > 0:
        al.error("code %s returned from '%s': %s" % (code, cmdline, output), "utils.html_to_pdf")
        return "ERROR"
    with open(outputfile.name, "r") as f:
        pdfdata = f.read()
    os.unlink(inputfile.name)
    os.unlink(outputfile.name)
    return pdfdata

def generate_label_pdf(dbo, locale, records, papersize, units, hpitch, vpitch, width, height, lmargin, tmargin, cols, rows):
    """
    Generates a PDF of labels from the rows given to the measurements provided.
    papersize can be "a4" or "letter"
    units can be "inch" or "cm"
    all units themselves should be floats, cols and rows should be ints
    """
    #from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4, inch, cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

    unit = inch
    if units == "cm":
        unit = cm
    psize = A4
    if papersize == "letter":
        psize = letter

    fout = StringIO()
    doc = SimpleDocTemplate(fout, pagesize=psize, leftMargin = lmargin * unit, topMargin = tmargin * unit, rightMargin = 0, bottomMargin = 0)
    col = 0
    row = 0
    elements = []

    def newData():
        l = []
        for dummy in range(0, rows):
            l.append( [ "" ] * cols )
        return l

    def addToData(rd, datad, cold, rowd):
        # Ref: http://bitboost.com/ref/internal-address-formats/
        template = "%(name)s\n%(address)s\n%(postcode)s %(town)s %(county)s"
        if locale in ( "en", "en_CA", "en_AU", "en_IN", "en_KA", "en_PH", "en_TH", "en_VN", "th" ):
            # US style, city/state/zip on last line
            template = "%(name)s\n%(address)s\n%(town)s %(county)s %(postcode)s"
        elif locale in ( "en_GB", "en_IE", "en_ZA" ):
            # UK style, postcode on last line
            template = "%(name)s\n%(address)s\n%(town)s\n%(county)s\n%(postcode)s"
        elif locale in ( "bs", "bg", "cs", "de", "el", "en_CN", "en_NZ", "es", 
            "es_EC", "en_MX", "es_MX", "fr", "he", "it", "lt", "nb", "nl", "pl", "pt", 
            "ru", "sk", "sl", "sv", "tr" ):
            # European style, postcode precedes city/state on last line
            template = "%(name)s\n%(address)s\n%(postcode)s %(town)s %(county)s"
        ad = template % { "name": str(rd["OWNERNAME"]).strip(), "address": rd["OWNERADDRESS"], "town": rd["OWNERTOWN"],
            "county": rd["OWNERCOUNTY"], "postcode": rd["OWNERPOSTCODE"] }
        #al.debug("Adding to data col=%d, row=%d, val=%s" % (cold, rowd, ad))
        datad[rowd][cold] = decode_html(ad)

    def addTable(datad):
        #al.debug("Adding data to table: " + str(datad))
        t = Table(datad, cols * [ hpitch * unit ], rows * [ vpitch * unit ])
        t.hAlign = "LEFT"
        t.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP")]))
        # If we have more than 8 labels vertically, use a smaller font
        if rows > 8:
            t.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"),
                                   ("FONTSIZE", (0,0), (-1,-1), 8)]))
        elements.append(t)

    data = newData()
    al.debug("creating mailing label PDF from %d rows" % len(records), "utils.generate_label_pdf", dbo)
    for r in records:
        addToData(r, data, col, row)
        # move to next label position
        col += 1
        if col == cols: 
            row += 1
            col = 0
            if row == rows:
                # We've filled the page, create the table and add it
                row = 0
                col = 0
                addTable(data)
                # reset the data for the next page
                data = newData()
                # TODO: Add pagebreak?

    # Add anything pending to the page
    addTable(data)
    # Build the PDF
    doc.build(elements)
    return fout.getvalue()

