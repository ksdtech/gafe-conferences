## GAFE Conference Manager
A Python-Flask-Google App Engine project bootstrapped from 
https://github.com/GoogleCloudPlatform/appengine-flask-skeleton

## Project Setup and Development Server Testing
To customize this project, you'll have to set up your own Google App Engine project in the
Google Developers Console.

1. Clone this repository.

2. Use the [Google Developers Console](https://console.developers.google.com) to create a
   project, with a unique app id. (App id and project id are identical)

3. Go to the API Manager section. On the APIs tab, Enable the Calendar, Google+ and Gmail APIs.
   On the Credentials tab, click "Add credentials" and create an OAuth 2.0 client ID. 
   Add "http://localhost:8080" to the "Authorized Javascript origins" and 
   "http://localhost:8080/oauth2callback" to the "Authorized redirect URIs".  
   Click the "Download JSON" button, rename the downloaded .json file to
   "client_secrets.json", and save it in the top level folder of your local repository.

4. [Possibly Add credentials for a "Service account" and download the JSON credentials
   to "service_account.json" in the top level folder of the repository.]   

5. On the "OAuth consent screen" tab, supply your email address and a display name for your
   app, like "My District GAFE Conference Manager". Add other information as necessary.

6. [Possibly verify your domain if you want to receive Calendar push notifications]

7. Install the [App Engine Python SDK](https://developers.google.com/appengine/downloads).
   See the README file for directions. You'll need python 2.7 and 
   [pip 1.4 or later](http://www.pip-installer.org/en/latest/installing.html) installed too.

8. Customize the "config-sample.py" file and save it as "config.py" in the top level 
   folder of the repository.

9. Install dependencies in the project's lib directory.
   Note: App Engine can only import libraries from inside your project directory.

   ```
   cd <project directory>
   rm -rf lib/*
   pip install -r requirements.txt -t lib
   ```

10. Run the project locally from the command line:

   ```
   dev_appserver.py -A gafe-conferences app.yaml
   ```

   or, if you want to empty a messed up datastore

   ```
   dev_appserver.py -A gafe-conferences  --clear_datastore yes app.yaml
   ```

Congratulations, your project should be running now!

Visit the application [http://localhost:8080](http://localhost:8080)

See [the development server documentation](https://developers.google.com/appengine/docs/python/tools/devserver)
for options when running dev_appserver.

## Deployment
To deploy the application on appspot.com:

1. In the [Google Developers Console](https://console.developers.google.com) console, add
   the appspot.com URIs for the "Authorized Javascript origins" and "Authorized redirect URIs". 

2. Modify the config.py file with the appropriate hostname, port and protocol.

3. [Deploy the
   application](https://developers.google.com/appengine/docs/python/tools/uploadinganapp) with

   ```
   appcfg.py -A <your-project-id> --oauth2 update .
   ```

Congratulations! Your application is now live at your-app-id.appspot.com

## Next Steps


### Feedback
Star this repo if you found it useful. Use the github issue tracker to give
feedback on this repo.

## Contributing changes
See [CONTRIB.md](CONTRIB.md) for information on developing apps on top of the Google Cloud
Platform.  If you have contributions or feature requests on the GAFE Conference Manager
project, please email the author, Peter Zingg, at pzingg -at- kentfieldschools -dot- org.

For information on the Python Flask Skeleton for Google App Engine,
a skeleton for building Python applications on Google App Engine with the
[Flask micro framework](http://flask.pocoo.org) and other related projects,
see the [Google Cloud Platform github repos](https://github.com/GoogleCloudPlatform).

## Licensing
See [LICENSE](LICENSE)

## Author
Python Flask Skeleton for Google App Engine: Logan Henriquez and Johan Euphrosine  
GAFE Conference Manager: Peter Zingg
