# Some helper functions
import os
import csv

from exampleapp.models import VancouverBikeRack, Content, ContentSignet

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_all():
    load_content()
    load_bikerack_data()
    create_users()

def load_content():

    ContentSignet.objects.all().delete()
    Content.objects.all().delete()
    for t in ['content 1', 'content 2']:
        c = Content(contents=t)
        c.save()

def load_bikerack_data():
    # clear all data
    VancouverBikeRack.objects.all().delete()

    # load the test data
    datafile = os.path.join(BASE_DIR, 'BikeRackData.csv')

    with open(datafile, newline='') as csvfile:
        next(csvfile)
        bike_racks = [
            VancouverBikeRack(None, *row)
            for row in csv.reader(csvfile)
        ]
        VancouverBikeRack.objects.bulk_create(bike_racks)


from django.contrib.auth.models import User

def create_users():
    if not User.objects.filter(username = 'admin').exists():
        User.objects.create_superuser('admin', password='password')

    for u in ['bigbird', 'ernie', 'bert']:
        if not User.objects.filter(username = u).exists():
            user = User.objects.create_user(username=u,
                                            password='password')
