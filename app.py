# Custom extension for IBM Watson Assistant which provides a
# REST API around a single database table 
#
# The code demonstrates how a simple REST API can be developed and
# then deployed as serverless app to IBM Cloud Code Engine.
#


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


# sample records to be inserted after table recreation
sample_certs=[
    {
        "employeename":"Patrick Dlamini",
        "certificatetype":"Microsoft",
        "certificatedescription":"Azure fundamentals: AZ-900",
        "certificatelink": "https://learn.microsoft.com/en-us/credentials/certifications/azure-fundamentals/?practice-assessment-type=certification",
        "expirydate":"2024-05-30",
        
    },
  

]


# Schema for table "CERTIFICATIONS"
# Set default schema to "CERTIFICATIONS"
class CertModel(db.Model):
    __tablename__ = 'PREFERENCES'
    __table_args__ = TABLE_ARGS
    title = db.Column('TITLE',db.String(500))
    link = db.Column('LINK',db.String(1000))
    category = db.Column('CATEGORY',db.String(150))
    
    

# the Python output for Certifications
class CertOutSchema(Schema):
    title = String()
    link = String()
    category = String()

   
    
   

# the Python input for Certifications
class CertInSchema(Schema):
    title = String(required=True)
    link = String(required=True)
    category = String(required=True)

    
# use with pagination
class CertQuerySchema(Schema):
    page = Integer(load_default=1)
    per_page = Integer(load_default=20, validate=Range(max=300))

class CerttsOutSchema(Schema):
    certs = List(Nested(CertOutSchema))
    pagination = Nested(PaginationSchema)

# register a callback to verify the token
@auth.verify_token  
def verify_token(token):
    if token in tokens:
        return tokens[token]
    else:
        return None

#retrieve records with same name 
@app.get('/preferences/preferences/<string:preferences>')
@app.output(CertOutSchema)
@app.auth_required(auth)
@app.input(CertQuerySchema, 'query')
def get_certs_by_name(preferences, query):
    """Get certifications by name
    Retrieve all certification records with the specified employee name
    """

    pagination = CertModel.query.filter(CertModel.preferences == preferences).paginate(
        page=query['page'],
        per_page=query['per_page']
    )
    def get_page_url(page):
        return url_for('get_certs_by_name', preferences=preferences, page=page, per_page=query['per_page'], _external=True)

    pagination_info = {
        'page': pagination.page,
        'per_page': pagination.per_page,
        'pages': pagination.pages,
        'total': pagination.total,
        'current': get_page_url(pagination.page),
        'first': get_page_url(1),
        'last': get_page_url(pagination.pages),
        'prev': get_page_url(pagination.prev_num) if pagination.has_prev else None,
        'next': get_page_url(pagination.next_num) if pagination.has_next else None
    }
    certs_data = {
        'certs': pagination.items,
        'pagination': pagination_info
    }

     # Start building the HTML table
    table_html = "<table border='4'><tr><th>Name</th><th>Certificate Type</th><th>Certificate Description</th><th>Certificate Link</th><th>Expiration Date</th></tr>"

    # Add each valid certification to the table
    for cert in certs_data['certs']:
         table_html += f"<tr><td>{html.escape(cert.employeename)}</td>" \
              f"<td>{html.escape(cert.certificatetype)}</td>" \
              f"<td>{html.escape(cert.certificatedescription)}</td>" \
              f"<td><a href='{html.escape(cert.certificatelink)}'>Link</a></td>" \
              f"<td>{html.escape(str(cert.expirydate))}</td></tr>"
        
    # Close the table
    table_html += "</table>"
    
    # Store the table in a variable
    Certs_table = table_html
    
    # Return the table as part of a JSON response
    return jsonify({
        "table": Certs_table,
        "pagination": certs_data['pagination'],
        "message": "Certification data retrieved successfully"
    })



# create a record
@app.post('/Preferences/create')
@app.input(CertInSchema, location='json')
@app.output(CertOutSchema, 201)
@app.auth_required(auth)
def create_record(data):
    """Insert a new record
    Insert a new record with the given attributes. Its new ID is returned.
    """
    cert = CertModel(**data)
    db.session.add(cert)
    db.session.commit()
    return cert



# default "homepage", also needed for health check by Code Engine
@app.get('/')
def print_default():
    """ Greeting
    health check
    """
    # returning a dict equals to use jsonify()
    return {'message': 'This is the certifications API server'}


# Start the actual app
# Get the PORT from environment or use the default
port = os.getenv('PORT', '5000')
if __name__ == "__main__":
    app.run(host='0.0.0.0',port=int(port))
