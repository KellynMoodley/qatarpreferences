import os
import ast
from dotenv import load_dotenv
from apiflask import APIFlask, Schema, HTTPTokenAuth, PaginationSchema, pagination_builder, abort
from apiflask.fields import Integer, String, Boolean, Date, List, Nested
from apiflask.validators import Length, Range
# Database access using SQLAlchemy
from flask_sqlalchemy import SQLAlchemy
from flask import abort, request, jsonify, url_for
import html
from datetime import datetime
from sqlalchemy import text, func
from sqlalchemy.sql import union_all
from sqlalchemy import or_

# Set how this API should be titled and the current version
API_TITLE='Events API for Watson Assistant'
API_VERSION='1.0.1'

# create the app
app = APIFlask(__name__, title=API_TITLE, version=API_VERSION)

# load .env if present
load_dotenv()

# the secret API key, plus we need a username in that record
API_TOKEN="{{'{0}':'appuser'}}".format(os.getenv('API_TOKEN'))
#convert to dict:
tokens=ast.literal_eval(API_TOKEN)

# database URI
DB2_URI=os.getenv('DB2_URI')
# optional table arguments, e.g., to set another table schema
ENV_TABLE_ARGS=os.getenv('TABLE_ARGS')
TABLE_ARGS=None
if ENV_TABLE_ARGS:
    TABLE_ARGS=ast.literal_eval(ENV_TABLE_ARGS)
else:
    # Setting default schema based on observed table name
    TABLE_ARGS={'schema': 'JYW20640'}


# specify a generic SERVERS scheme for OpenAPI to allow both local testing
# and deployment on Code Engine with configuration within Watson Assistant
app.config['SERVERS'] = [
    {
        'description': 'Code Engine deployment',
        'url': 'https://{appname}.{projectid}.{region}.codeengine.appdomain.cloud',
        'variables':
        {
            "appname":
            {
                "default": "myapp",
                "description": "application name"
            },
            "projectid":
            {
                "default": "projectid",
                "description": "the Code Engine project ID"
            },
            "region":
            {
                "default": "us-south",
                "description": "the deployment region, e.g., us-south"
            }
        }
    },
    {
        'description': 'local test',
        'url': 'http://127.0.0.1:{port}',
        'variables':
        {
            'port':
            {
                'default': "5000",
                'description': 'local port to use'
            }
        }
    }
]


# set how we want the authentication API key to be passed
auth=HTTPTokenAuth(scheme='ApiKey', header='API_TOKEN')

# configure SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI']=DB2_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Initialize SQLAlchemy for our database
db = SQLAlchemy(app)


# Schema for table "PREFERENCES"
class PreferenceModel(db.Model):
    __tablename__ = 'PREFERENCES'
    __table_args__ = TABLE_ARGS
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column('TITLE', db.String(500))
    link = db.Column('LINK', db.String(1000))
    category = db.Column('CATEGORY', db.String(150))
    
    

# the Python output for Preferences
class PreferenceOutSchema(Schema):
    title = String()
    link = String()
    category = String()

   

# the Python input for Preferences
class PreferenceInSchema(Schema):
    title = String(required=True)
    link = String(required=True)
    category = String(required=True)


# register a callback to verify the token
@auth.verify_token  
def verify_token(token):
    if token in tokens:
        return tokens[token]
    else:
        return None

# Retrieve records by category
@app.get('/preferences/category/<string:category>')
@app.output(PreferenceOutSchema(many=True))
@app.auth_required(auth)
def get_preferences_by_category(category):
    """Get preferences by category"""
    preferences = PreferenceModel.query.filter_by(category=category).all()

    # Start building the HTML table
    table_html = "<table border='4'><tr><th>Charity name</th><th>Link to website</th></tr>"
    
    
    # Add each preference to the table
    for pref in preferences:
        table_html += f"<tr><td>{html.escape(pref.title)}</td>" \
          f"<td><a href='{html.escape(pref.link)}'>Link</a></td></tr>" 

        
    # Close the table
    table_html += "</table>"

    # Store the table in a variable
    valid_pref_table = table_html
    
    # Return all data without pagination
    return jsonify({
        "table": valid_pref_table,
        "message": "Preference data retrieved successfully",
        "total_records": len(preferences)
    })

# Create a record
@app.post('/preferences/create')
@app.input(PreferenceInSchema, location='json')
@app.output(PreferenceOutSchema, 201)
@app.auth_required(auth)
def create_record(data):
    """Insert a new record"""
    preference = PreferenceModel(**data)
    db.session.add(preference)
    db.session.commit()
    return preference


# default "homepage", also needed for health check by Code Engine
@app.get('/')
def print_default():
    """ Greeting
    health check
    """
    # returning a dict equals to use jsonify()
    return {'message': 'This is the preferences API server'}


# Start the actual app
# Get the PORT from environment or use the default
port = os.getenv('PORT', '5000')
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(port))
