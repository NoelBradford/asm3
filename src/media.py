#!/usr/bin/python

import al
import animal
import audit
import base64
import configuration
import datetime
import dbfs
from PIL import ExifTags, Image
import log
import os
import tempfile
import utils
import zipfile
from cStringIO import StringIO
from sitedefs import SCALE_PDF_DURING_ATTACH, SCALE_PDF_CMD

ANIMAL = 0
LOSTANIMAL = 1
FOUNDANIMAL = 2
PERSON = 3
WAITINGLIST = 5
ANIMALCONTROL = 6

MEDIATYPE_FILE = 0
MEDIATYPE_DOCUMENT_LINK = 1
MEDIATYPE_VIDEO_LINK = 2

def mime_type(filename):
    """
    Returns the mime type for a file with the given name
    """
    types = {
        "jpg"           : "image/jpeg",
        "jpeg"          : "image/jpeg",
        "bmp"           : "image/bmp",
        "gif"           : "image/gif",
        "png"           : "image/png",
        "doc"           : "application/msword",
        "xls"           : "application/vnd.ms-excel",
        "ppt"           : "application/vnd.ms-powerpoint",
        "docx"          : "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx"          : "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "xslx"          : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "odt"           : "application/vnd.oasis.opendocument.text",
        "sxw"           : "application/vnd.oasis.opendocument.text",
        "ods"           : "application/vnd.oasis.opendocument.spreadsheet",
        "odp"           : "application/vnd.oasis.opendocument.presentation",
        "pdf"           : "application/pdf",
        "mpg"           : "video/mpg",
        "mp3"           : "audio/mpeg3",
        "avi"           : "video/avi"
    }
    ext = filename[filename.rfind(".")+1:].lower()
    if ext in types:
        return types[ext]
    return "application/octet-stream"

def get_web_preferred_name(dbo, linktype, linkid):
    return dbo.query_string("SELECT MediaName FROM media " \
        "WHERE LinkTypeID = ? AND WebsitePhoto = 1 AND LinkID = ?", (linktype, linkid))

def get_web_preferred(dbo, linktype, linkid):
    return dbo.query("SELECT * FROM media WHERE LinkTypeID = ? AND " \
        "WebsitePhoto = 1 AND LinkID = ?", (linktype, linkid))

def get_media_by_seq(dbo, linktype, linkid, seq):
    """ Returns image media by a one-based sequence number. 
        Element 1 is always the preferred.
        Empty list is returned if the item doesn't exist
    """
    rows = dbo.query("SELECT * FROM media " \
        "WHERE LinkTypeID = ? AND LinkID = ? " \
        "AND MediaMimeType = 'image/jpeg' " \
        "AND (ExcludeFromPublish = 0 OR ExcludeFromPublish Is Null) " \
        "ORDER BY WebsitePhoto DESC, ID", (linktype, linkid))
    if len(rows) >= seq:
        return [rows[seq-1],]
    else:
        return []

def get_total_seq(dbo, linktype, linkid):
    return dbo.query_int(dbo, "SELECT COUNT(ID) FROM media WHERE LinkTypeID = ? AND LinkID = ? " \
        "AND MediaMimeType = 'image/jpeg' " \
        "AND (ExcludeFromPublish = 0 OR ExcludeFromPublish Is Null)", (linktype, linkid))

def set_video_preferred(dbo, username, mid):
    """
    Makes the media with id the preferred for video in the link
    """
    link = dbo.first_row(dbo.query("SELECT LinkID, LinkTypeID FROM media WHERE ID = ?", [mid]))
    dbo.update("media", "LinkID=%d AND LinkTypeID=%d" % (link.LINKID, link.LINKTYPEID), { "WebsiteVideo": 0 })
    dbo.update("media", mid, { "WebsiteVideo": 1, "Date": dbo.now() }, username, setLastChanged=False) 

def set_web_preferred(dbo, username, mid):
    """
    Makes the media with id the preferred for the web in the link
    """
    link = dbo.first_row(dbo.query("SELECT LinkID, LinkTypeID FROM media WHERE ID = ?", [mid]))
    dbo.update("media", "LinkID=%d AND LinkTypeID=%d" % (link.LINKID, link.LINKTYPEID), { "WebsitePhoto": 0 })
    dbo.update("media", mid, { "WebsitePhoto": 1, "ExcludeFromPublish": 0, "Date": dbo.now() }, username, setLastChanged=False) 

def set_doc_preferred(dbo, username, mid):
    """
    Makes the media with id the preferred for docs in the link
    """
    link = dbo.first_row(dbo.query("SELECT LinkID, LinkTypeID FROM media WHERE ID = ?", [mid]))
    dbo.update("media", "LinkID=%d AND LinkTypeID=%d" % (link.LINKID, link.LINKTYPEID), { "DocPhoto": 0 })
    dbo.update("media", mid, { "DocPhoto": 1, "Date": dbo.now() }, username, setLastChanged=False) 

def set_excluded(dbo, username, mid, exclude = 1):
    """
    Marks the media with id excluded from publishing.
    """
    dbo.update("media", mid, { "ExcludeFromPublish": exclude, "Date": dbo.now() }, username, setLastChanged=False)

def get_name_for_id(dbo, mid):
    return dbo.query_string("SELECT MediaName FROM media WHERE ID = ?", [mid])

def get_notes_for_id(dbo, mid):
    return dbo.query_string("SELECT MediaNotes FROM media WHERE ID = ?", [mid])

def get_media_file_data(dbo, mid):
    """
    Gets a piece of media by id. Returns None if the media record does not exist.
    id: The media id
    Returns a tuple containing the last modified date, media name, 
    mime type and file data
    """
    mm = get_media_by_id(dbo, mid)
    if len(mm) == 0: return (None, "", "", "")
    mm = mm[0]
    return mm.DATE, mm.MEDIANAME, mm.MEDIAMIMETYPE, dbfs.get_string(dbo, mm.MEDIANAME)

def get_image_file_data(dbo, mode, iid, seq = 0, justdate = False):
    """
    Gets an image
    mode: animal | media | animalthumb | person | personthumb | dbfs
    iid: The id of the animal for animal/thumb mode or the media record
        or a template path for dbfs mode
    seq: If the mode is animal or person, returns image X for that person/animal
         The first image is always the preferred photo and seq is 1-based.
    if justdate is True, returns the last modified date
    if justdate is False, returns a tuple containing the last modified date and image data
    """
    def nopic():
        NOPIC_DATE = datetime.datetime(2011, 1, 1)
        if justdate: return NOPIC_DATE
        return (NOPIC_DATE, "NOPIC")
    def thumb_nopic():
        NOPIC_DATE = datetime.datetime(2011, 1, 1)
        if justdate: return NOPIC_DATE
        return (NOPIC_DATE, "NOPIC")
    def mrec(mm):
        if len(mm) == 0: return nopic()
        if justdate: return mm[0].DATE
        return (mm[0].DATE, dbfs.get_string(dbo, mm[0].MEDIANAME))
    def thumb_mrec(mm):
        if len(mm) == 0: return thumb_nopic()
        if justdate: return mm[0].DATE
        return (mm[0].DATE, scale_thumbnail(dbfs.get_string(dbo, mm[0].MEDIANAME)))

    if mode == "animal":
        if seq == 0:
            return mrec( get_web_preferred(dbo, ANIMAL, int(iid)) )
        else:
            return mrec( get_media_by_seq(dbo, ANIMAL, int(iid), seq) )

    elif mode == "person":
        if seq == 0:
            return mrec( get_web_preferred(dbo, PERSON, int(iid)) )
        else:
            return mrec( get_media_by_seq(dbo, PERSON, int(iid), seq) )

    elif mode == "animalthumb":
        return thumb_mrec( get_web_preferred(dbo, ANIMAL, int(iid)) )

    elif mode == "personthumb":
        return thumb_mrec( get_web_preferred(dbo, PERSON, int(iid)) )

    elif mode == "media":
        return mrec( get_media_by_id(dbo, int(iid)) )

    elif mode == "dbfs":
        if justdate:
            return dbo.now()
        else:
            if str(iid).startswith("/"):
                # Complete path was given
                return (dbo.now(), dbfs.get_string_filepath(dbo, str(iid)))
            else:
                # Only name was given
                return (dbo.now(), dbfs.get_string(dbo, str(iid)))

    elif mode == "nopic":
        if dbfs.file_exists(dbo, "nopic.jpg"):
            return (dbo.now(), dbfs.get_string_filepath(dbo, "/reports/nopic.jpg"))
        else:
            return (dbo.now(), utils.read_binary_file(dbo.installpath + "media/reports/nopic.jpg"))

    else:
        return nopic()

def get_dbfs_path(linkid, linktype):
    path = "/animal/%d" % int(linkid)
    if linktype == PERSON:
        path = "/owner/%d" % int(linkid)
    elif linktype == LOSTANIMAL:
        path = "/lostanimal/%d" % int(linkid)
    elif linktype == FOUNDANIMAL:
        path = "/foundanimal/%d" % int(linkid)
    elif linktype == WAITINGLIST:
        path = "/waitinglist/%d" % int(linkid)
    elif linktype == ANIMALCONTROL:
        path = "/animalcontrol/%d" % int(linkid)
    return path

def get_log_from_media_type(x):
    """ Returns the corresponding log type for a media type """
    m = {
        ANIMAL: log.ANIMAL,
        PERSON: log.PERSON,
        LOSTANIMAL: log.LOSTANIMAL,
        FOUNDANIMAL: log.FOUNDANIMAL,
        WAITINGLIST: log.WAITINGLIST,
        ANIMALCONTROL: log.ANIMALCONTROL
    }
    return m[x]

def get_media(dbo, linktype, linkid):
    return dbo.query("SELECT * FROM media WHERE LinkTypeID = ? AND LinkID = ? ORDER BY Date DESC", ( linktype, linkid ))

def get_media_by_id(dbo, mid):
    return dbo.query("SELECT * FROM media WHERE ID = ?", [mid] )

def get_image_media(dbo, linktype, linkid, ignoreexcluded = False):
    if not ignoreexcluded:
        return dbo.query("SELECT * FROM media WHERE LinkTypeID = ? AND LinkID = ? " \
            "AND (LOWER(MediaName) Like '%%.jpg' OR LOWER(MediaName) Like '%%.jpeg') ORDER BY media.Date DESC", ( linktype, linkid ))
    else:
        return dbo.query("SELECT * FROM media WHERE (ExcludeFromPublish = 0 OR ExcludeFromPublish Is Null) " \
            "AND LinkTypeID = ? AND LinkID = ? AND (LOWER(MediaName) Like '%%.jpg' OR LOWER(MediaName) Like '%%.jpeg') ORDER BY media.Date DESC", ( linktype, linkid ))

def attach_file_from_form(dbo, username, linktype, linkid, post):
    """
    Attaches a media file from the posted form
    data is the web.py data object and should contain
    comments and either the filechooser object, with filename and value 
    OR filedata, filetype and filename parameters (filetype is the MIME type, filedata is base64 encoded contents)
    """
    ext = ""
    filedata = post["filedata"]
    filename = post["filename"]
    comments = post["comments"]
    if filedata != "":
        filetype = post["filetype"]
        if filetype.startswith("image") or filename.lower().endswith(".jpg"): ext = ".jpg"
        elif filetype.startswith("image") or filename.lower().endswith(".png"): ext = ".png"
        elif filetype.find("pdf") != -1 or filename.lower().endswith(".pdf"): ext = ".pdf"
        elif filetype.find("html") != -1 or filename.lower().endswith(".html"): ext = ".html"
        # Strip the data:mime prefix so we just have base64 data
        if filedata.startswith("data:"):
            filedata = filedata[filedata.find(",")+1:]
            # Browser escaping turns base64 pluses back into spaces, so switch back
            filedata = filedata.replace(" ", "+")
        filedata = base64.b64decode(filedata)
        al.debug("received data URI '%s' (%d bytes)" % (filename, len(filedata)), "media.attach_file_from_form", dbo)
        if ext == "":
            msg = "could not determine extension from file.type '%s', abandoning" % filetype
            al.error(msg, "media.attach_file_from_form", dbo)
            raise utils.ASMValidationError(msg)
    else:
        # It's a traditional form post with a filechooser, we should make
        # it the default web/doc picture after posting if none is available.
        ext = post.filename()
        ext = ext[ext.rfind("."):].lower()
        filedata = post.filedata()
        filename = post.filename()
        al.debug("received POST file data '%s' (%d bytes)" % (filename, len(filedata)), "media.attach_file_from_form", dbo)

    # If we receive some images in formats other than JPG, we'll
    # pretend they're jpg as that's what they'll get transformed into
    # by scale_image
    if ext == ".png":
        ext = ".jpg"

    mediaid = dbo.get_id("media")
    medianame = "%d%s" % ( mediaid, ext )
    ispicture = ext == ".jpg" or ext == ".jpeg"
    ispdf = ext == ".pdf"
    excludefrompublish = 0
    if configuration.auto_new_images_not_for_publish(dbo) and ispicture:
        excludefrompublish = 1

    # Are we allowed to upload this type of media?
    if ispicture and not configuration.media_allow_jpg(dbo):
        msg = "upload of media type jpg is disabled"
        al.error(msg, "media.attach_file_from_form", dbo)
        raise utils.ASMValidationError(msg)
    if ispdf and not configuration.media_allow_pdf(dbo):
        msg = "upload of media type pdf is disabled"
        al.error(msg, "media.attach_file_from_form", dbo)
        raise utils.ASMValidationError(msg)

    # Is it a picture?
    if ispicture:
        # Autorotate it to match the EXIF orientation
        filedata = auto_rotate_image(dbo, filedata)
        # Scale it down to the system set size
        scalespec = configuration.incoming_media_scaling(dbo)
        if scalespec != "None":
            filedata = scale_image(filedata, scalespec)
            al.debug("scaled image to %s (%d bytes)" % (scalespec, len(filedata)), "media.attach_file_from_form", dbo)

    # Is it a PDF? If so, compress it if we can and the option is on
    if ispdf and SCALE_PDF_DURING_ATTACH and configuration.scale_pdfs(dbo):
        orig_len = len(filedata)
        filedata = scale_pdf(filedata)
        if len(filedata) < orig_len:
            al.debug("compressed PDF (%d bytes)" % (len(filedata)), "media.attach_file_from_form", dbo)

    # Attach the file in the dbfs
    path = get_dbfs_path(linkid, linktype)
    dbfsid = dbfs.put_string(dbo, medianame, path, filedata)

    # Are the notes for an image blank and we're defaulting them from animal comments?
    if comments == "" and ispicture and linktype == ANIMAL and configuration.auto_media_notes(dbo):
        comments = animal.get_comments(dbo, int(linkid))
        # Are the notes blank and we're defaulting them from the filename?
    elif comments == "" and configuration.default_media_notes_from_file(dbo):
        comments = utils.filename_only(filename)
    
    # Create the media record
    dbo.insert("media", {
        "ID":                   mediaid,
        "DBFSID":               dbfsid,
        "MediaSize":            len(filedata),
        "MediaName":            medianame,
        "MediaMimeType":        mime_type(medianame),
        "MediaType":            0,
        "MediaNotes":           comments,
        "WebsitePhoto":         0,
        "WebsiteVideo":         0,
        "DocPhoto":             0,
        "ExcludeFromPublish":   excludefrompublish,
        # ASM2_COMPATIBILITY
        "NewSinceLastPublish":  1,
        "UpdatedSinceLastPublish": 0,
        # ASM2_COMPATIBILITY
        "LinkID":               linkid,
        "LinkTypeID":           linktype,
        "Date":                 dbo.now(),
        "RetainUntil":          None
    }, username, setCreated=False, generateID=False)

    # Verify this record has a web/doc default if we aren't excluding it from publishing
    if ispicture and excludefrompublish == 0:
        check_default_web_doc_pic(dbo, mediaid, linkid, linktype)

    return mediaid

def attach_link_from_form(dbo, username, linktype, linkid, post):
    """
    Attaches a link to a web resource from a form
    """
    existingvid = dbo.query_int("SELECT COUNT(*) FROM media WHERE WebsiteVideo = 1 " \
        "AND LinkID = ? AND LinkTypeID = ?", (linkid, linktype))
    defvid = 0
    if existingvid == 0 and post.integer("linktype") == MEDIATYPE_VIDEO_LINK:
        defvid = 1
    url = post["linktarget"]
    if url.find("://") == -1:
        url = "http://" + url
    al.debug("attached link %s" % url, "media.attach_file_from_form")
    return dbo.insert("media", {
        "DBFSID":               0,
        "MediaSize":            0,
        "MediaName":            url,
        "MediaMimeType":        "text/url",
        "MediaType":            post.integer("linktype"),
        "MediaNotes":           post["comments"],
        "WebsitePhoto":         0,
        "WebsiteVideo":         defvid,
        "DocPhoto":             0,
        "ExcludeFromPublish":   0,
        # ASM2_COMPATIBILITY
        "NewSinceLastPublish":  1,
        "UpdatedSinceLastPublish": 0,
        # ASM2_COMPATIBILITY
        "LinkID":               linkid,
        "LinkTypeID":           linktype,
        "Date":                 dbo.now(),
        "RetainUntil":          None
    }, username, setCreated=False)

def check_default_web_doc_pic(dbo, mediaid, linkid, linktype):
    """
    Checks if linkid/type has a default pic for the web or documents. If not,
    sets mediaid to be the default.
    """
    existing_web = dbo.query_int("SELECT COUNT(*) FROM media WHERE WebsitePhoto = 1 " \
        "AND LinkID = ? AND LinkTypeID = ?", (linkid, linktype))
    existing_doc = dbo.query_int("SELECT COUNT(*) FROM media WHERE DocPhoto = 1 " \
        "AND LinkID = ? AND LinkTypeID = ?", (linkid, linktype))
    if existing_web == 0:
        dbo.update("media", mediaid, { "WebsitePhoto": 1 })
    if existing_doc == 0:
        dbo.update("media", mediaid, { "DocPhoto": 1 })

def create_blank_document_media(dbo, username, linktype, linkid):
    """
    Creates a new media record for a blank document for the link given.
    linktype: ANIMAL, PERSON, etc
    linkid: ID for the link
    returns the new media id
    """
    mediaid = dbo.get_id("media")
    path = get_dbfs_path(linkid, linktype)
    name = str(mediaid) + ".html"
    dbfsid = dbfs.put_string(dbo, name, path, "")
    dbo.insert("media", {
        "ID":                   mediaid,
        "DBFSID":               dbfsid,
        "MediaSize":            0,
        "MediaName":            "%d.html" % mediaid,
        "MediaMimeType":        "text/html",
        "MediaType":            0,
        "MediaNotes":           "New document",
        "WebsitePhoto":         0,
        "WebsiteVideo":         0,
        "DocPhoto":             0,
        "ExcludeFromPublish":   0,
        # ASM2_COMPATIBILITY
        "NewSinceLastPublish":  1,
        "UpdatedSinceLastPublish": 0,
        # ASM2_COMPATIBILITY
        "LinkID":               linkid,
        "LinkTypeID":           linktype,
        "Date":                 dbo.now(),
        "RetainUntil":          None
    }, username, setCreated=False, generateID=False)
    return mediaid

def create_document_media(dbo, username, linktype, linkid, template, content):
    """
    Creates a new media record for a document for the link given.
    linktype: ANIMAL, PERSON, etc
    linkid: ID for the link
    template: The name of the template used to create the document
    content: The document contents
    """
    mediaid = dbo.get_id("media")
    path = get_dbfs_path(linkid, linktype)
    name = str(mediaid) + ".html"
    dbfsid = dbfs.put_string(dbo, name, path, content)
    dbo.insert("media", {
        "ID":                   mediaid,
        "DBFSID":               dbfsid,
        "MediaSize":            len(content),
        "MediaName":            "%d.html" % mediaid,
        "MediaMimeType":        "text/html",
        "MediaType":            0,
        "MediaNotes":           template,
        "WebsitePhoto":         0,
        "WebsiteVideo":         0,
        "DocPhoto":             0,
        "ExcludeFromPublish":   0,
        # ASM2_COMPATIBILITY
        "NewSinceLastPublish":  1,
        "UpdatedSinceLastPublish": 0,
        # ASM2_COMPATIBILITY
        "LinkID":               linkid,
        "LinkTypeID":           linktype,
        "Date":                 dbo.now(),
        "RetainUntil":          None
    }, username, setCreated=False, generateID=False)
    return mediaid

def create_log(dbo, user, mid, logcode = "UK00", message = ""):
    """
    Creates a log message related to media
    mid: The media ID
    logcode: The fixed code for reports to use - 
        ES01 = Document signing request
        ES02 = Document signed
    message: Some human readable text to accompany the code
    """
    m = dbo.first_row(get_media_by_id(dbo, mid))
    if m is None: return
    logtypeid = configuration.generate_document_log_type(dbo)
    log.add_log(dbo, user, get_log_from_media_type(m.LINKTYPEID), m.LINKID, logtypeid, "%s:%s:%s - %s" % (logcode, m.ID, message, m.MEDIANOTES))

def sign_document(dbo, username, mid, sigurl, signdate):
    """
    Signs an HTML document.
    sigurl: An HTML5 data: URL containing an image of the signature
    """
    al.debug("signing document %s for %s" % (mid, username), "media.sign_document", dbo)
    SIG_PLACEHOLDER = "signature:placeholder"
    date, medianame, mimetype, content = get_media_file_data(dbo, mid)
    # Is this an HTML document?
    if content.find("<p") == -1 and content.find("<td") == -1:
        al.error("document %s is not HTML" % mid, "media.sign_document", dbo)
        raise utils.ASMValidationError("Cannot sign a non-HTML document")
    # Has this document already been signed? 
    if 0 != dbo.query_int("SELECT COUNT(*) FROM media WHERE ID = ? AND SignatureHash Is Not Null AND SignatureHash <> ''", [mid]):
        al.error("document %s has already been signed" % mid, "media.sign_document", dbo)
        raise utils.ASMValidationError("Document is already signed")
    # Does the document have a signing placeholder image? If so, replace it
    if content.find(SIG_PLACEHOLDER) != -1:
        al.debug("document %s: found signature placeholder" % mid, "media.sign_document", dbo)
        content = content.replace(SIG_PLACEHOLDER, sigurl)
    else:
        # Create the signature at the foot of the document
        al.debug("document %s: no placeholder, appending" % mid, "media.sign_document", dbo)
        sig = "<hr />\n"
        sig += '<p><img src="' + sigurl + '" /></p>\n'
        sig += "<p>%s</p>\n" % signdate
        content += sig
    # Create a hash of the contents and store it with the media record
    dbo.update("media", mid, { "SignatureHash": utils.md5_hash(content) })
    # Update the dbfs contents
    update_file_content(dbo, username, mid, content)

def has_signature(dbo, mid):
    """ Returns true if a piece of media has a signature """
    return 0 != dbo.query_int("SELECT COUNT(*) FROM media WHERE SignatureHash Is Not Null AND SignatureHash <> '' AND ID = ?", [mid])

def update_file_content(dbo, username, mid, content):
    """
    Updates the dbfs content for the file pointed to by id
    """
    dbfs.replace_string(dbo, content, get_name_for_id(dbo, mid))
    dbo.update("media", mid, { "Date": dbo.now(), "MediaSize": len(content) }, username, setLastChanged=False)

def update_media_notes(dbo, username, mid, notes):
    dbo.update("media", mid, { 
        "MediaNotes": notes,
        "Date":       dbo.now(),
        # ASM2_COMPATIBILITY
        "UpdatedSinceLastPublish": 1
    }, username, setLastChanged=False)

def delete_media(dbo, username, mid):
    """
    Deletes a media record from the system
    """
    mr = dbo.first_row(dbo.query("SELECT * FROM media WHERE ID=?", [mid]))
    if not mr: return
    try:
        dbfs.delete(dbo, mr.MEDIANAME)
    except Exception as err:
        al.error(str(err), "media.delete_media", dbo)
    dbo.delete("media", mid, username)
    # Was it the web or doc preferred? If so, make the first image for the link
    # the web or doc preferred instead
    if mr.WEBSITEPHOTO == 1:
        ml = dbo.first_row(dbo.query("SELECT * FROM media WHERE LinkID = ? AND LinkTypeID = ? " \
            "AND MediaMimeType = 'image/jpeg' " \
            "ORDER BY ID", (mr.LINKID, mr.LINKTYPEID)))
        if ml: dbo.update("media", ml.ID, { "WebsitePhoto": 1 })
    if mr.DOCPHOTO == 1:
        ml = dbo.first_row(dbo.query("SELECT * FROM media WHERE LinkID = ? AND LinkTypeID = ? " \
            "AND MediaMimeType = 'image/jpeg' " \
            "ORDER BY ID", (mr.LINKID, mr.LINKTYPEID)))
        if ml: dbo.update("media", ml.ID, { "DocPhoto": 1 })

def rotate_media(dbo, username, mid, clockwise = True):
    """
    Rotates an image media record 90 degrees if clockwise is true, or 270 degrees if false
    """
    mr = dbo.first_row(dbo.query("SELECT * FROM media WHERE ID=?", [mid]))
    if not mr: raise utils.ASMError("Record does not exist")
    # If it's not a jpg image, we can stop right now
    mn = mr.MEDIANAME
    ext = mn[mn.rfind("."):].lower()
    if ext != ".jpg" and ext != ".jpeg":
        raise utils.ASMError("Image is not a JPEG file, cannot rotate")
    # Load the image data
    path = get_dbfs_path(mr.LINKID, mr.LINKTYPEID)
    imagedata = dbfs.get_string(dbo, mn, path)
    imagedata = rotate_image(imagedata, clockwise)
    # Store it back in the dbfs and add an entry to the audit trail
    dbfs.put_string(dbo, mn, path, imagedata)
    # Update the date stamp on the media record
    dbo.update("media", mid, { "Date": dbo.now(), "MediaSize": len(imagedata) })
    audit.edit(dbo, username, "media", mid, "", "media id %d rotated, clockwise=%s" % (mid, str(clockwise)))

def scale_image(imagedata, resizespec):
    """
    Produce a scaled version of an image. 
    imagedata - The image to scale
    resizespec - a string in WxH format
    returns the scaled image data
    """
    try:
        # Turn the scalespec into a tuple of the largest side
        ws, hs = resizespec.split("x")
        w = int(ws)
        h = int(hs)
        size = w, w
        if h > w: size = h, h
        # Load the image data into a StringIO object and scale it
        file_data = StringIO(imagedata)
        im = Image.open(file_data)
        im.thumbnail(size, Image.ANTIALIAS)
        # Save the scaled down image data into another string for return
        output = StringIO()
        im.save(output, "JPEG")
        scaled_data = output.getvalue()
        output.close()
        return scaled_data
    except Exception as err:
        al.error("failed scaling image: %s" % str(err), "media.scale_image")
        return imagedata

def auto_rotate_image(dbo, imagedata):
    """
    Automatically rotate an image according to the orientation of the
    image in the EXIF data. 
    """
    try:
        inputd = StringIO(imagedata)
        im = Image.open(inputd)
        for orientation in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation] == "Orientation":
                break
        if not hasattr(im, "_getexif") or im._getexif() is None:
            al.debug("image has no EXIF data, abandoning rotate", "media.auto_rotate_image", dbo)
            return imagedata
        exif = dict(im._getexif().items())
        if exif[orientation] == 3:   im = im.transpose(Image.ROTATE_180)
        elif exif[orientation] == 6: im = im.transpose(Image.ROTATE_270)
        elif exif[orientation] == 8: im = im.transpose(Image.ROTATE_90)
        output = StringIO()
        im.save(output, "JPEG")
        rotated_data = output.getvalue()
        output.close()
        return rotated_data
    except Exception as err:
        al.error("failed rotating image: %s" % str(err), "media.auto_rotate_image", dbo)
        return imagedata

def rotate_image(imagedata, clockwise = True):
    """
    Rotate an image. 
    clockwise: Rotate 90 degrees clockwise, if false rotates anticlockwise
    """
    try:
        inputd = StringIO(imagedata)
        im = Image.open(inputd)
        if clockwise:
            im = im.transpose(Image.ROTATE_270)
        else:
            im = im.transpose(Image.ROTATE_90)
        output = StringIO()
        im.save(output, "JPEG")
        rotated_data = output.getvalue()
        output.close()
        return rotated_data
    except Exception as err:
        al.error("failed rotating image: %s" % str(err), "media.rotate_image")
        return imagedata

def remove_expired_media(dbo, username = "system"):
    """
    Removes all media where retainuntil < today
    and document media older than today - remove document media years
    """
    rows = dbo.query("SELECT ID, DBFSID FROM media WHERE RetainUntil Is Not Null AND RetainUntil < ?", [ dbo.today() ])
    for r in rows:
        dbfs.delete_id(r.dbfsid) 
    dbo.execute("DELETE FROM media WHERE RetainUntil Is Not Null AND RetainUntil < ?", [ dbo.today() ])
    al.debug("removed %d expired media items (retain until)" % len(rows), "media.remove_expired_media", dbo)
    if configuration.auto_remove_document_media(dbo):
        years = configuration.auto_remove_document_media_years(dbo)
        if years > 0:
            cutoff = dbo.today(years * -365)
            rows = dbo.query("SELECT ID, DBFSID FROM media WHERE MediaType = ? AND MediaMimeType <> 'image/jpeg' AND Date < ?", ( MEDIATYPE_FILE, cutoff ))
            for r in rows:
                dbfs.delete_id(r.dbfsid) 
            dbo.execute("DELETE FROM media WHERE MediaType = ? AND MediaMimeType <> 'image/jpeg' AND Date < ?", ( MEDIATYPE_FILE, cutoff ))
            al.debug("removed %d expired document media items (remove after years)" % len(rows), "media.remove_expired_media", dbo)

def scale_thumbnail(imagedata):
    """
    Scales the given imagedata down to slightly larger than our thumbnail size 
    (150px on the longest side)
    """
    return scale_image(imagedata, "150x150")

def scale_image_file(inimage, outimage, resizespec):
    """
    Scales the given image file from inimage to outimage
    to the size given in resizespec
    """
    # If we haven't been given a valid resizespec,
    # use a default value.
    if resizespec.count("x") != 1:
        resizespec = "640x640"
    # Turn the scalespec into a tuple of the largest side
    ws, hs = resizespec.split("x")
    w = int(ws)
    h = int(hs)
    size = w, w
    if h > w: size = h, h
    # Scale and save
    im = Image.open(inimage)
    im.thumbnail(size, Image.ANTIALIAS)
    im.save(outimage, "JPEG")

def scale_thumbnail_file(inimage, outimage):
    """
    Scales the given image to a thumbnail
    """
    scale_image_file(inimage, outimage, "150x150")

def scale_pdf(filedata):
    """
    Scales the given PDF filedata down and returns the compressed PDF data.
    """
    # If there are more than 50 pages, it's going to take forever to scale -
    # don't even bother trying. 
    pagecount = utils.pdf_count_pages(filedata)
    if pagecount > 50:
        al.error("Abandon PDF scaling - has > 50 pages (%s found)" % pagecount, "media.scale_pdf")
        return filedata
    inputfile = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    outputfile = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    inputfile.write(filedata)
    inputfile.flush()
    inputfile.close()
    outputfile.close()
    # If something went wrong during the scaling, use the original data
    if not scale_pdf_file(inputfile.name, outputfile.name):
        return filedata
    compressed = utils.read_binary_file(outputfile.name)
    os.unlink(inputfile.name)
    os.unlink(outputfile.name)
    # If something has gone wrong and the scaled one has no size, return the original
    if len(compressed) == 0:
        return filedata
    # If the original is smaller than the scaled one, return the original
    if len(compressed) > len(filedata):
        return filedata
    return compressed

def scale_odt(filedata):
    """
    Scales an ODT file down by stripping anything starting with the name "Object"
    in the root or in the "ObjectReplacements" folder. Everything in the "Pictures"
    folder is also removed.
    """
    odt = StringIO(filedata)
    try:
        zf = zipfile.ZipFile(odt, "r")
    except zipfile.BadZipfile:
        return ""
    # Write the replacement file
    zo = StringIO()
    zfo = zipfile.ZipFile(zo, "w", zipfile.ZIP_DEFLATED)
    for info in zf.infolist():
        # Skip any object or image files to save space
        if info.filename.startswith("ObjectReplacements/Object ") or info.filename.startswith("Object ") or info.filename.endswith(".jpg") or info.filename.endswith(".png"):
            pass
        else:
            zfo.writestr(info.filename, zf.open(info.filename).read())
    zf.close()
    zfo.close()
    # Return the zip data
    return zo.getvalue()

def scale_pdf_file(inputfile, outputfile):
    """
    Scale a PDF file using the command line. There are different
    approaches to this and gs, imagemagick and pdftk (among others)
    can be used.
    Returns True for success or False for failure.
    """
    KNOWN_ERRORS = [ 
        # GS produces this with out of date libpoppler and Microsoft Print PDF
        "Can't find CMap Identity-UTF16-H building a CIDDecoding resource." 
    ]
    code, output = utils.cmd(SCALE_PDF_CMD % { "output": outputfile, "input": inputfile})
    for e in KNOWN_ERRORS:
        # Any known errors in the output should return failure
        if output.find(e) != -1: 
            al.error("Abandon PDF scaling - found known error: %s" % e, "media.scale_pdf_file")
            return False
    # A nonzero exit code is a failure
    if code > 0: 
        al.error("Abandon PDF scaling - nonzero exit code (%s)" % code, "media.scale_pdf_file")
        return False
    return True
   
def scale_all_animal_images(dbo):
    """
    Goes through all animal images in the database and scales
    them to the current incoming media scaling factor.
    """
    mp = dbo.query("SELECT ID, MediaName FROM media WHERE MediaMimeType = 'image/jpeg' AND LinkTypeID = 0")
    for i, m in enumerate(mp):
        filepath = dbo.query_string("SELECT Path FROM dbfs WHERE Name = ?", [m.MEDIANAME])
        name = str(m.MEDIANAME)
        inputfile = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        outputfile = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        odata = dbfs.get_string(dbo, name)
        inputfile.write(odata)
        inputfile.flush()
        inputfile.close()
        outputfile.close()
        al.debug("scaling %s (%d of %d)" % (name, i, len(mp)), "media.scale_all_animal_images", dbo)
        try:
            scale_image_file(inputfile.name, outputfile.name, configuration.incoming_media_scaling(dbo))
        except Exception as err:
            al.error("failed scaling image, doing nothing: %s" % err, "media.scale_all_animal_images", dbo)
            continue
        data = utils.read_binary_file(outputfile.name)
        os.unlink(inputfile.name)
        os.unlink(outputfile.name)
        # Update the image file data
        dbfs.put_string(dbo, name, filepath, data)
        dbo.update("media", m.ID, { "MediaSize": len(data) })
    al.debug("scaled %d images" % len(mp), "media.scale_all_animal_images", dbo)

def scale_all_odt(dbo):
    """
    Goes through all odt files attached to records in the database and 
    scales them down (throws away images and objects so only the text remains to save space)
    """
    mo = dbo.query("SELECT ID, MediaName FROM media WHERE MediaMimeType = 'application/vnd.oasis.opendocument.text'")
    total = 0
    for i, m in enumerate(mo):
        name = str(m.MEDIANAME)
        al.debug("scaling %s (%d of %d)" % (name, i, len(mo)), "media.scale_all_odt", dbo)
        odata = dbfs.get_string(dbo, name)
        if odata == "":
            al.error("file %s does not exist" % name, "media.scale_all_odt", dbo)
            continue
        path = dbo.query_string("SELECT Path FROM dbfs WHERE Name = ?", [name])
        ndata = scale_odt(odata)
        if len(ndata) < 512:
            al.error("scaled odt %s came back at %d bytes, abandoning" % (name, len(ndata)), "scale_all_odt", dbo)
        else:
            dbfs.put_string(dbo, name, path, ndata)
            dbo.update("media", m.ID, { "MediaSize": len(ndata) }) 
            total += 1
    al.debug("scaled %d of %d odts" % (total, len(mo)), "media.scale_all_odt", dbo)

def scale_all_pdf(dbo):
    """
    Goes through all PDFs in the database and attempts to scale them down.
    """
    mp = dbo.query("SELECT ID, MediaName FROM media WHERE MediaMimeType = 'application/pdf' ORDER BY ID DESC")
    total = 0
    for i, m in enumerate(mp):
        dbfsid = dbo.query_string("SELECT ID FROM dbfs WHERE Name = ?", [m.MEDIANAME])
        odata = dbfs.get_string_id(dbo, dbfsid)
        data = scale_pdf(odata)
        al.debug("scaling %s (%d of %d): old size %d, new size %d" % (m.MEDIANAME, i, len(mp), len(odata), len(data)), "check_and_scale_pdfs", dbo)
        # Store the new compressed PDF file data - if it's smaller
        if len(data) < len(odata):
            dbfs.put_string_id(dbo, dbfsid, m.MEDIANAME, data)
            dbo.update("media", m.ID, { "MediaSize": len(data) })
            total += 1
    al.debug("scaled %d of %d pdfs" % (total, len(mp)), "media.scale_all_pdf", dbo)


