import os
import json
import pickle
import joblib
import pandas as pd
from flask import Flask, jsonify, request
from peewee import (
    Model, IntegerField, FloatField,
    TextField, IntegrityError
)
from playhouse.shortcuts import model_to_dict
from playhouse.db_url import connect


########################################
# Begin database stuff

# The connect function checks if there is a DATABASE_URL env var.
# If it exists, it uses it to connect to a remote postgres db.
# Otherwise, it connects to a local sqlite db stored in predictions.db.
DB = connect(os.environ.get('DATABASE_URL') or 'sqlite:///predictions.db')

class Prediction(Model):
    observation_id = IntegerField(unique=True)
    observation = TextField()
    proba = FloatField()
    true_class = IntegerField(null=True)

    class Meta:
        database = DB


DB.create_tables([Prediction], safe=True)

# End database stuff
########################################

########################################
# Unpickle the previously-trained model


with open('/tmp/columns.json') as fh:
    columns = json.load(fh)

pipeline = joblib.load('/tmp/pipeline.pickle')

with open('/tmp/dtypes.pickle', 'rb') as fh:
    dtypes = pickle.load(fh)


# End model un-pickling
########################################


########################################
# Begin webserver stuff

app = Flask(__name__)


@app.route('/predict', methods=['POST'])
def predict():
    # Flask provides a deserialization convenience function called
    # get_json that will work if the mimetype is application/json.
    obs_dict = request.get_json()
    _id = obs_dict['id']
    observation = obs_dict['observation']
    print(observation)
    print(columns)
    print(dtypes)
    # Now do what we already learned in the notebooks about how to transform
    # a single observation into a dataframe that will work with a pipeline.
    try:
        obs = pd.DataFrame([observation], columns=columns).astype(dtypes)
 
        # Now get ourselves an actual prediction of the positive class.
        proba = pipeline.predict_proba(obs)[0, 1]
        response = {'proba': proba}
        p = Prediction(
            observation_id=_id,
            proba=proba,
            observation=request.data
        )
        try:
            p.save()
        except IntegrityError:
            error_msg = 'Observation ID: "{}" already exists'.format(_id)
            response['error'] = error_msg
            response['proba'] = proba
            output=jsonify(response)
            print(output)
            DB.rollback()
    except:
        response= {'error':'Observation is invalid!'}
    return jsonify(response)


@app.route('/update', methods=['POST'])
def update():
    obs = request.get_json()
    try:
        p = Prediction.get(Prediction.observation_id == obs['id'])
        p.true_class = obs['true_class']
        p.save()
        return jsonify(model_to_dict(p))
    except Prediction.DoesNotExist:
        error_msg = 'Observation ID: "{}" does not exist'.format(obs['id'])
        return jsonify({'error': error_msg})


@app.route('/list-db-contents')
def list_db_contents():
    return jsonify([
        model_to_dict(obs) for obs in Prediction.select()
    ])


# End webserver stuff
########################################

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True, port=5000)
