# Some helper functions

from tests.exampleapp.models import VancouverBikeRack, Content, ContentSignet
import pandas as pd

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
    df = pd.read_csv('BikeRackData.csv')
    for row in df.iterrows():
        l = VancouverBikeRack(row[0],
                              row[1][0],
                              row[1][1],
                              row[1][2],
                              row[1][3],
                              row[1][4],
                              row[1][5],
                              row[1][6],
                              row[1][7],
                              row[1][8],
                              row[1][9],
                              row[1][10])
        l.save()


from django.contrib.auth.models import User

def create_users():
    if not User.objects.filter(username = 'admin').exists():
        User.objects.create_superuser('admin', password='password')

    for u in ['bigbird', 'ernie', 'bert']:
        if not User.objects.filter(username = u).exists():
            user = User.objects.create_user(username=u,
                                            password='password')




