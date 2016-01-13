## iOSDeploy
Python script to deploy an ad-hoc iOS application to Dropbox service

### Installation
Place all the files in this repository in your iOS project directory and within a `iosdeploy` folder

### Requirments
- OS X 10.9+
- Python 2.7 (usually shipped with OS X)
- Dropbox app key and app secret with Full Dropbox access

### Setup

#### Configurations
To setup the deployment, run the following commands on your iOS project directory...

```
python iosdeploy/deploy.py --setup
```

then follow the on-screen instructions.

After the setup, a `.iosdeploy` file will be created within the iOS project directory. This file contains sensitive informations such as app key, app secret and/or access token, which can be used to access your entire Dropbox files. To prevent this informations reveal to the public, it is recommended that **the `.iosdeploy` file should be ignored on the version control and `--store-app-info` should not be set in the setup process**.

If you want to let other people to deploy your application, just send your `.iosdeploy` file to them using a secured channel.

#### iOS Project Integration
In the `Build Phases` of your desired target, add a new `Run Script Phase` and paste in the command below...

```
python iosdeplay/deploy.py
```

This should let the Xcode run the command after finish building your iOS project.

In order to deploy the iOS application, `.ipa` file should be built within the "Binary Path" as specified in the setup process. This step can be automated by using `gym` from fastlane tools.

### Deployment
To deploy manually, run...

```
python iosdeploy/deploy.py
```

Options for the deployment can be access via `python iosdeploy/deploy.py --help` command.