# Readme 

## What is Satchmo Payment Module Paysbuy?
It is a custom payment module for use with Satchmo Project. It functions as middleware between the Satchmo backend and PaySbuy.com's payment API.
This module is not part of the official satchmo repository. If you want to use this payment module you will have to follow the installation instructions below.
PaySbuy is a online payment gateway operated in Thailand and is currently the only online payment gateway(as far as I know) that accepts transfers to and from Thai banking institutions. From their website: "PAYSBUY is an online payment service that allows sending money as easy as sending email. Members can instantly and securely send money to anyone with an email address and a bank account in Thailand."
##### This software may be outdated. It was last tested in 2013 on Satchmo-0.9.3 with Paysbuy API v3.01. Also, see known issues below.

## Docs
This section is incomplete. If there is information that you think belongs here, please feel free to fork this and submit a pull request with your changes.
Documentation for the PaySbuy API can be found in the ```Reference/``` directory. At the time of this writing, more documentation can be found at https://www.paysbuy.com/download.aspx?p=2
This module was written based on the specifications in post_merchant_integration_manual_v301_en.pdf
At the time of this writing, documentation for Satchmo is no longer available for download from satchmoproject.com. As such, I have included a [somewhat dated] copy in the ```Reference/``` directory.

### Installation
This sub-section is incomplete. If there is information that you think belongs here, please feel free to fork this and submit a pull request with your changes.
In order to get this module working, you will have to copy files to the appropriate directories in your project, update your settings.py, and update your database; in that order.
Templates go in ```'src/satchmo/satchmo/apps/payment/templates/shop/checkout/paysbuy/'```.
models.py, views.py, processor.py, config.py, and __init__.py all go in ```'src/satchmo/satchmo/apps/payment/modules/paysbuy/'```
In your settings.py, add ```'payment.modules.paysbuy',``` to the ```INSTALLED_APPS``` tuple.
And remember, before restarting satchmo, you may have to remove some old .pyc files (settings.pyc for sure). This can be done easily using ```rm``` or ```pyclean```.
Then, restart your satchmo instance and update your database.

### Configuration
In order to accept real payments via PaySbuy, you will need to configure your PaySbuy merchant details in the "Site Settings" section of the admin area of your store. Help text will display next to the input fields to help you change the default values.

### Known Issues
PaySbuy itself has some quirks that developers should be aware of:
    *Their docs and support don't always match up with the API's actual functionality. You will have to experiment
    *Their API sometimes dumps the user into an ASP.NET stack trace instead of providing error messages. Not sure if this is only on the demo server or on the production server as well.
    *I remember having a heck of a time getting credit cards to work due to some difference between the demo server and the production server. I can't remember what it was, but just be aware that there may be some issues there.

## Contributing
If you'd like to contribute to the the Satchmo Project please go to the official repository at https://bitbucket.org/chris1610/satchmo and read their instructions for contributing.
If you'd like to improve this module directly, feel free to fork and submit a pull request with your changes. Here are some basic guidelines for coding style of you want to contribute to this module:
  Please make sure that your code is consistent with PEP8. See https://www.python.org/dev/peps/pep-0008/ for details.
  Naming conventions:
    1. all_functions_methods_and_local_vars_will_be_named_like_this
    2. ALL_EXTRA_GLOBALS_WILL_BE_LIKE_THIS
    3. all local variables that = request.POST[something] will start with psb_front_ or psb_back
 
### To Do
I would like to add functionality to easily change which version of the PaySbuy API this module is trying to communicate with, just in case PaySbuy changes their API.
Improve the docs!
Some unit tests and built in testing functionality with sample data would be nice. :)

## Contributors
Morgan Shorter-Mcfarlane(Author): https://github.com/MorganShorter
A big thanks to all the people who helped me create this module!

