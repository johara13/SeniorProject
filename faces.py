

"""Returns likely emotions based on person's face"""

import argparse
import base64
import webapp2
import jinja2
import os
import urllib
from PIL import Image
from PIL import ImageDraw

#from google.appengine.ext import vendor
#vendor.add('lib')

from googleapiclient import discovery
import httplib2
from oauth2client.client import GoogleCredentials
from fileinput import filename

DEFAULT_INPUTTXT = 'face2.jpg'

JINJA_ENVIRONMENT = jinja2.Environment(
    loader= jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)
# [START get_vision_service]
DISCOVERY_URL='https://{api}.googleapis.com/$discovery/rest?version={apiVersion}'


def get_vision_service():
    credentials = GoogleCredentials.get_application_default()
    return discovery.build('vision', 'v1', credentials=credentials,
                           discoveryServiceUrl=DISCOVERY_URL)
# [END get_vision_service]


# [START detect_face]
def detect_face(image_content, max_results=1):
    """Uses the Vision API to detect faces in the given file.
    Args:
        face_file: A file-like object containing an image with faces.
    Returns:
        An array of dicts with information about the faces in the picture.
    """
    batch_request = [{
        'image': {
            'content': base64.b64encode(image_content).decode('UTF-8')
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

    faceAnnotations = response['responses'][0]['faceAnnotations']
    return faceAnnotations[0]
# [END detect_face]


# [START highlight_faces]

RATINGS = ['LIKELY','VERY_LIKELY']

def likely_sentiment(face):
    if face['joyLikelihood'] in RATINGS:
        return 'JOY'
    if face['sorrowLikelihood'] in RATINGS:
        return 'SORROW'
    if face['angerLikelihood'] in RATINGS:
        return 'ANGER'
    if face['surpriseLikelihood'] in RATINGS:
        return 'SURPRISE'
# [END highlight_faces]

def main(imageurl):
     with open(imageurl, 'rb') as image:
            result1 = lambda_handler({'image': image.read()}, None)
            result  = result1['likely_sentiment']
            #self.response.write(result)
            return result


# [START main]
def lambda_handler(event, context):
    face = detect_face(event['image'])
    return {
        'likely_sentiment':likely_sentiment(face)
    }
# [END main]
class MainPage(webapp2.RequestHandler):
    def get(self):
        #self.response.write('Hello, webapp2')
        #print 'Hello World'
        imageurl = self.request.get('inputtxt',DEFAULT_INPUTTXT)    
        result = main(imageurl)
        template_values = { 'result': result,
                           'inputtxt': imageurl}
        template = JINJA_ENVIRONMENT.get_template('index.html')
        self.response.write(template.render(template_values))

class UploadImage(webapp2.RequestHandler):
    def post(self):
        imageurl = self.request.get('inputtxt',DEFAULT_INPUTTXT)        
        self.redirect('/?'+urllib.urlencode({'inputtxt' : imageurl})) 

        
app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/sign', UploadImage)
    ], debug = True)
#if __name__ == '__main__':
    #parser = argparse.ArgumentParser(
    #    description='Detects faces in the given image.')
    #parser.add_argument(
     #   'input_image', help='the base 64 encoded image you\'d like to detect faces in.')
    #args = parser.parse_args()

    #with open(args.input_image, 'rb') as image:
    
