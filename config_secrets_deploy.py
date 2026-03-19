# Roostoo API Keys — DO NOT COMMIT THIS FILE
import datetime

# Auto-switch to competition API on March 21
_COMPETITION_START = datetime.date(2026, 3, 21)

if datetime.date.today() >= _COMPETITION_START:
    # Round 1 Competition API
    API_KEY = "jzOcMlJYtb13bEEBHW24UZ2s0e0iirtMq5Fkak3G98GIfe8vIgBl7onLgXXMe5ca"
    SECRET_KEY = "TtYHYEjIr3I2it3Gc51tJ5aRctwfDrH22MlhXfjxGKco5Nyqw0VlzgMpQf6kaIaK"
else:
    # Testing API (verified March 19)
    API_KEY = "dBl0EwNBCwt5f1MtSEIIRGNu8CRaYo7R768WxFJUArRjMDCcs9Z29WWk243jEun7"
    SECRET_KEY = "jBiSp17sddHk78l6ES5u8fpeMyettLlITyQ1ATGzuEeCi4mCt6kvadWREwLCZ9S3"
