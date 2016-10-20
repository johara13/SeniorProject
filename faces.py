

"""Returns likely emotions based on person's face"""

import argparse
from google.appengine.ext import vendor
vendor.add('lib')
import base64
import webapp2
import logging
import jinja2
import os
import cStringIO
import urllib
from PIL import Image
from PIL import ImageDraw
import cloudstorage as gcs    
from google.appengine.api import app_identity
from googleapiclient import discovery
import httplib2
from oauth2client.client import GoogleCredentials
from fileinput import filename
from google.appengine.api import images

from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers

DEFAULT_INPUTTXT = 'face2.jpg'

JINJA_ENVIRONMENT = jinja2.Environment(
    loader= jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)
# [START get_vision_service]
DISCOVERY_URL='https://{api}.googleapis.com/$discovery/rest?version={apiVersion}'

my_default_retry_params = gcs.RetryParams(initial_delay=0.2,
                                          max_delay=5.0,
                                          backoff_factor=2,
                                          max_retry_period=15)
gcs.set_default_retry_params(my_default_retry_params)


def get_vision_service():
    credentials = GoogleCredentials.get_application_default()
    return discovery.build('vision', 'v1', credentials=credentials,
                           discoveryServiceUrl=DISCOVERY_URL)

def detect_face(image_content, max_results=4):
    #uses vision api to detect faces in image
    #args: image_content, Image file
    
    #converts image file to base64 and passes it to Vision API
    buffer = cStringIO.StringIO()
    image_content.save(buffer, format="JPEG")
    img_str = base64.b64encode(buffer.getvalue())
    
    batch_request = [{
        'image': {
            #'content': base64.b64encode(image_content).decode('UTF-8')
            'content': img_str.decode('UTF-8')
            },
        'features': [{
            'type': 'FACE_DETECTION',
            'maxResults': max_results,
            }]
        }]
    service = get_vision_service()
    request = service.images().annotate(body={
        'requests': batch_request,
        })
    response = request.execute()
    if response['responses'] and 'faceAnnotations' in response['responses'][0]:
        faceAnnotations = response['responses'][0]['faceAnnotations']
        return faceAnnotations
    
    else:
        return None

RATINGS = ['LIKELY','VERY_LIKELY']

def highlight_faces(image, faces, output_filename):
    """Draws a polygon around the faces, then saves to output_filename.

    Args:
      image: a file containing the image with the faces.
      faces: a list of faces found in the file. This should be in the format
          returned by the Vision API.
      output_filename: the name of the image file to be created, where the
          faces have polygons drawn around them.
    """
    im = image
    draw = ImageDraw.Draw(im)

    for face in faces:
        box = [(v.get('x', 0.0), v.get('y', 0.0))
               for v in face['fdBoundingPoly']['vertices']]
        draw.line(box + [box[0]], width=5, fill='#00ff00')

    return im

def likely_sentiment(face):
    #returns the sentiment felt in the face data
    if face['joyLikelihood'] in RATINGS:
        return 'JOY'
    if face['sorrowLikelihood'] in RATINGS:
        return 'SORROW'
    if face['surpriseLikelihood'] in RATINGS:
        return 'SURPRISE'
    if face['angerLikelihood'] in RATINGS:
        return 'ANGER'
    

def main(imageurl):
    #opens image and passes it to lambda handler, returning the emotion felt
    blob_reader = blobstore.BlobReader(imageurl)
    img = Image.open(blob_reader)
    result = lambda_handler(img, None)
    return result

def lambda_handler(event, context):
    #passes image to detect_face and returns dictionary with likelysentiment
    face = detect_face(event, 4)
    if not face:
        return None
    else:
        result = {}
        n = 0
        for f in face:
            result[n] = likely_sentiment(f)
            n = n+1
        return result

class MainPage(webapp2.RequestHandler):
    #the landing page
    def get(self):
        upload_url = blobstore.create_upload_url('/upload')
        template_values = { 'upload_url' : upload_url}
        template = JINJA_ENVIRONMENT.get_template('index.html')
        self.response.write(template.render(template_values))

class UploadImage(blobstore_handlers.BlobstoreUploadHandler):
    #handles file uploads
    def post(self):   
        upload_files = self.get_uploads()
        blob_info = upload_files[0]
        self.redirect('/serve/%s' % blob_info.key())
        
class ServeHandler(blobstore_handlers.BlobstoreDownloadHandler):
    #displays uploaded file and results
    def get(self, photo_key):
        if not blobstore.get(photo_key):
            self.error(404)
        else:  
            upload_url = blobstore.create_upload_url('/upload')        
            result = main(photo_key)
            blob_reader = blobstore.BlobReader(photo_key)
            img = Image.open(blob_reader)
            faces = detect_face(img,4)
            if faces:
                im = highlight_faces(img, faces,"out.jpg")
                buffer = cStringIO.StringIO()
                im.save(buffer, format="JPEG")
            else:
                buffer = cStringIO.StringIO()
                img.save(buffer, format="JPEG")
            img_str = base64.b64encode(buffer.getvalue()).decode('UTF-8')
            template_values = { 'result': result,
                                'ifile': img_str,
                                'upload_url' : upload_url
                                }
            template = JINJA_ENVIRONMENT.get_template('index.html')
            self.response.write(template.render(template_values))

        
app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/upload', UploadImage),
    ('/serve/([^/]+)?', ServeHandler)
    ], debug = True)

    
