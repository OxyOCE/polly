import os
import yaml

with open(os.path.join(os.getcwd(), './config/secrets.yaml'), 'r') as fp:
    SECRETS = yaml.load(fp, Loader=yaml.FullLoader)
