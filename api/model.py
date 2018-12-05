from flask_restplus import Namespace, Resource, fields
from werkzeug.datastructures import FileStorage
from flask import make_response
from PIL import Image
import io
import glob
import os
import shutil
from flask import abort
from config import MODEL_META_DATA
from core.backend import ModelWrapper
from api.pre_process import alignMain


api = Namespace('model', description='Model information and inference operations')

model_meta = api.model('ModelMetadata', {
    'id': fields.String(required=True, description='Model identifier'),
    'name': fields.String(required=True, description='Model name'),
    'description': fields.String(required=True, description='Model description'),
    'license': fields.String(required=False, description='Model license')
})


@api.route('/metadata')
class Model(Resource):
    @api.doc('get_metadata')
    @api.marshal_with(model_meta)
    def get(self):
        """Return the metadata associated with the model"""
        return MODEL_META_DATA


# Creating a JSON response model: https://flask-restplus.readthedocs.io/en/stable/marshalling.html#the-api-model-factory
label_prediction = api.model('LabelPrediction', {
    'label_id': fields.String(required=False, description='Label identifier'),
    'label': fields.String(required=True, description='Class label'),
    'probability': fields.Float(required=True)
})


# Set up parser for input data (http://flask-restplus.readthedocs.io/en/stable/parsing.html)
input_parser = api.parser()
# Example parser for file input
input_parser.add_argument('file', type=FileStorage, location='files', required=True)
input_parser.add_argument('mask_type', type=str, default='all',
             choices=('random', 'center', 'left', 'grid'),
             help='Mask Types')

@api.route('/predict')
class Predict(Resource):

    model_wrapper = ModelWrapper()

    @api.doc('predict')
    @api.expect(input_parser)
    def post(self):
        """Make a prediction given input data"""
        result = {'status': 'error'}

        args = input_parser.parse_args()
        image_input_read = Image.open(args['file'])
        image_mask_type = args['mask_type']
        # creating directory for storing input
        input_directory = '/workspace/assets/input/file'
        if not os.path.exists(input_directory):
            os.mkdir(input_directory)
        # clear input directory
        input_folder = '/workspace/assets/input/file/'
        for file in glob.glob(input_folder + '*'):
            try:
                try:
                    os.remove(file)
                except:
                    shutil.rmtree(file)
            except:
                continue
        # save input image
        image_input_read.save('/workspace/assets/input/file/input.jpg')
        # face detection, alignment and resize using openface
        args = {
               'inputDir':input_directory,
               'outputDir':'/workspace/assets/input/file/align',
               'landmarks':'innerEyesAndBottomLip',
               'dlibFacePredictor':'/workspace/openface/models/dlib/shape_predictor_68_face_landmarks.dat',
               'verbose':True,
                'size':64,
                'skipMulti':False,
                'fallbackLfw':None,
                'mode':'align'
               }
        try:
            alignMain(args)
        except:
            #abort if there face is not detected
            abort(400, 'Invalid input.')

        # store aligned input
        input_data = '/workspace/assets/input/file/align/file/input.png'
        #
        image_path = self.model_wrapper.predict(input_data, image_mask_type)
        """
        preparing image collage
        """
        new_collage_path = "/workspace/assets/center_mask/completed/Collage.jpg"
        img_columns = 5
        img_rows = 4
        img_width = 320
        img_height = 256
        thumbnail_width = img_width//img_columns
        thumbnail_height = img_height//img_rows
        size = thumbnail_width, thumbnail_height
        new_collage = Image.new('RGB', (img_width, img_height))
        images_list = []
        filenames = []
        for filename in glob.glob(image_path):
            filenames.append(filename)
        
        filenames.sort()
        for i in filenames:
            im=Image.open(i)
            im.thumbnail(size)
            images_list.append(im)
        
        i = 0
        x = 0
        y = 0
        for col in range(img_columns):
            for row in range(img_rows):
                new_collage.paste(images_list[i], (x, y))
                i += 1
                y += thumbnail_height
            x += thumbnail_width
            y = 0

        new_collage.save(new_collage_path)
                
        """
        end of collage creation process
        """
        img = Image.open(new_collage_path, mode='r')
        imgByteArr = io.BytesIO()
        img.save(imgByteArr, format='JPEG')
        imgByteArr = imgByteArr.getvalue()

        response = make_response(imgByteArr)
        response.headers.set('Content-Type', 'image/jpeg')
        response.headers.set('Content-Disposition', 'attachment', filename='result.jpg')
     

        return response
