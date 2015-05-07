import datetime
from decimal import Decimal
from django.conf import settings
from django.core import urlresolvers
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.http import urlencode
from django.utils.translation import ugettext as _
from django.views.decorators.cache import never_cache
from livesettings import config_get_group, config_value
from payment.config import gateway_live
from payment.utils import get_processor_by_key
from payment.views import payship
from satchmo_store.shop.models import Cart
from satchmo_store.shop.models import Order, OrderPayment
from satchmo_store.contact.models import Contact
from satchmo_utils.dynamic import lookup_url, lookup_template
from satchmo_utils.views import bad_or_missing
from sys import exc_info
from traceback import format_exception
import logging
import urllib2
from django.views.decorators.csrf import csrf_exempt

payment_module = config_get_group('PAYMENT_PAYSBUY')#group
log = logging.getLogger()

def custom_logger(custom_log_args, custom_logfile):
    custom_log_timestamp = datetime.datetime.now()
    custom_log = open(custom_logfile,'a')
    custom_log.write('%s\n' % custom_log_timestamp);
    custom_log.write('%s\n' % custom_log_args);
    custom_log.close()
    return True


def pay_ship_info(request):
    return payship.base_pay_ship_info(request,
        config_get_group('PAYMENT_PAYSBUY'), payship.simple_pay_ship_process_form, 
        'shop/checkout/paysbuy/pay_ship.html')
pay_ship_info = never_cache(pay_ship_info)


def confirm_info(request):
    try:
        order = Order.objects.from_request(request)
    except Order.DoesNotExist:
        url = lookup_url(payment_module, 'satchmo_checkout-step1')
        return HttpResponseRedirect(url)

    tempCart = Cart.objects.from_request(request)
    if tempCart.numItems == 0 and not order.is_partially_paid:
        template = lookup_template(payment_module, 'shop/checkout/empty_cart.html')
        return render_to_response(template,
                                  context_instance=RequestContext(request))

    # Check if the order is still valid
    if not order.validate(request):
        context = RequestContext(request,
                                 {'message': _('Your order is no longer valid.')})
        return render_to_response('shop/404.html', context_instance=context)
    # from here on just setting and calling variables
    template = lookup_template(payment_module, 'shop/checkout/paysbuy/confirm.html')
    if payment_module.LIVE.value:
        log.debug("live order on %s", payment_module.KEY.value)
        url = payment_module.CONNECTION.value 
        psb = payment_module.PSB.value
        account = payment_module.BIZ.value
        secure_code = payment_module.SECURE_CODE.value
    else:
        url = payment_module.CONNECTION_TEST.value
        psb = payment_module.PSB_TEST.value
        account = payment_module.BIZ_TEST.value
        secure_code = payment_module.SECURE_CODE_TEST.value
    try:
        address = lookup_url(payment_module,
            payment_module.FRONT_URL.value, include_server=True)
    except urlresolvers.NoReverseMatch:
        address = payment_module.FRONT_URL.value
    try:
        cart = Cart.objects.from_request(request)
    except:
        cart = None
    try:
        contact = Contact.objects.from_request(request)
    except:
        contact = None
    if cart and contact:
        cart.customer = contact
        log.debug(':::Updating Cart %s for %s' % (cart, contact))
        cart.save()
    if payment_module.OPT_FIX_REDIRECT.value:
        opt_fix_redirect = '1'
    else:
        opt_fix_redirect= ''
    if  payment_module.OPT_FIX_METHOD.value:
        opt_fix_method = '1'
    else:
        opt_fix_method = ''
    
    total_plus_tax = 0
    for o in order.orderitem_set.all():
        total_plus_tax = total_plus_tax + o.total_with_tax
    processor_module = payment_module.MODULE.load_module('processor')
    processor = processor_module.PaymentProcessor(payment_module)
    processor.create_pending_payment(order=order)
    ship_tax_total = total_plus_tax + order.shipping_cost

    psb_post_out_dict = {
     'order': order,
     'post_url': url,
     'psb': psb[:10],
     'biz': account[:200],
     'secure_code': secure_code[:200],
     'amount': ship_tax_total,
     'paypal': ""[:2],
     'commission': payment_module.COMMISSION_CODE.value[:200],
     'default_pay_method': payment_module.PAY_METHOD.value[:1],
     'currencyCode': payment_module.CURRENCY_CODE.value,
     'lang': payment_module.LANGUAGE.value[:1],
     'postURL': address[:500],
     'reqURL': payment_module.BACK_URL.value[:500],
     'opt_fix_redirect': opt_fix_redirect[:1],
     'opt_fix_method': opt_fix_method[:1],
     'opt_name': contact.full_name[:200],
     'opt_email': contact.email[:200],
     'opt_mobile': str(contact.primary_phone)[:200],
     'opt_address': str(contact.shipping_address)[:200],
     'opt_detail': ""[:200],
     'invoice': str(order.id)[:200],
     'itm': "Thailand Furniture Purchase"[:200],
     'PAYMENT_LIVE' : payment_module.LIVE.value,
     'OrderPaidInFull': order.paid_in_full,
    }

    ctx = RequestContext(request, psb_post_out_dict)
    if not payment_module.LIVE.value:
        if order.notes:
            admin_notes = order.notes + u'\n'
        else:
            admin_notes = ""
        order.notes = admin_notes + 'TEST' + u'\n'
    order.add_status(status='New', notes=_("Payment sent to Paysbuy."))
    order.save()
    if not payment_module.LIVE.value or payment_module.EXTRA_LOGGING.value:
        custom_logger(psb_post_out_dict, '%s/psb-confirm_info.log' % payment_module.PSB_LOGS_DIR)
    return render_to_response(template, context_instance=ctx)
confirm_info = never_cache(confirm_info)


@csrf_exempt
def psb_back_resp(request): 
    """ Cornfirms that payment has been completed and marks invoice as paid."""
    #   When you debug this function, remember to use satchmo.log;
    # otherwise, you have no way of knowing whats going on. :)
    
    # payment method response codes
    psb_pay_methods_dict = {
    '01': 'PAYSBUY Account',
    '02': 'Credit Card',
    '03': 'PayPal',
    '04': 'American Express',
    '05': 'Online Banking',
    '06': 'Counter Service'
    }
   
    if not payment_module.LIVE.value or payment_module.EXTRA_LOGGING.value:
        custom_logger(request, '%s/psb_back_resp.log' % payment_module.PSB_LOGS_DIR)

    try:
        psb_back_data = request.POST
        psb_back_fee = psb_back_data['fee']
        psb_back_amt = psb_back_data['amt']
        psb_back_result = psb_back_data['result']
        psb_back_txn_id = psb_back_data['apCode']
        psb_back_method = psb_back_data['method']
        try:
            psb_back_desc = psb_back_data['desc']
        except:
            psb_back_desc = False
        try:
            psb_back_confirm_cs = psb_back_data['confirm_cs']
        except:
            psb_back_confirm_cs = False
        psb_back_x_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if psb_back_x_for:
            psb_back_ip = psb_back_x_for
        else:
            psb_back_ip = request.META.get('REMOTE_ADDR')
        success_code = psb_back_result[:2]
        invoice = psb_back_result[2:]
        success_code_array = {
        '00': 'Billed',
        '02': 'In Process',
        '99': 'Blocked',
        }
        log.debug("Paysbuy response data: " + repr(psb_back_data))

        gross = float(psb_back_amt)
        # Update the order's status in the admin.
        if psb_back_confirm_cs:
            order = Order.objects.get(pk=invoice)
            order.add_status(status=success_code_array[success_code], 
            notes=success_code_array[success_code])
            order.save()
        if success_code == '99':
            if not psb_back_desc:
                temp_psb_back_desc = ''
            payment = processor.record_failure( amount=gross, 
            transaction_id=psb_back_txn_id, reason_code=success_code, 
            order=order, details=temp_psb_back_desc,)
        if not OrderPayment.objects.filter(transaction_id=psb_back_txn_id).count():
            # If the payment hasn't already been processed:
            order = Order.objects.get(pk=invoice)
            
            order.add_status(status=success_code_array[success_code], 
                            notes=_("Processing through Paysbuy:")) 
            processor = get_processor_by_key('PAYMENT_PAYSBUY')
            payment = processor.record_payment(order=order, amount=gross, 
            transaction_id=psb_back_txn_id, reason_code=success_code,)
            
            if order.notes:
                admin_notes = order.notes + u'\n'
            else:
                admin_notes = ''
            if psb_back_desc:
                desc_placeholder = psb_back_desc + u'\n' 
            else:
                desc_placeholder = ''
            order.notes = (admin_notes + _('---Comment via Paysbuy API---') + 
                    u'\n' + desc_placeholder + 'Paid by: ' + 
                    psb_pay_methods_dict[psb_back_method] + u'\n' + 
                    success_code_array[success_code] + u'\n' + u'\n' + 
                    'PAYSBUY FEE: ' + psb_back_fee + u'\n' + u'\n' + 
                    'PAYSBUY IP: ' + psb_back_ip )
            order.save()
            
            log.debug("Saved order notes from Paysbuy")

    except:
        log.exception(''.join(format_exception(*exc_info())))

    return HttpResponse()

def psb_front_resp(request):
    if not payment_module.LIVE.value or payment_module.EXTRA_LOGGING.value:
        custom_logger(request, '%s/psb_front_resp.log' % payment_module.PSB_LOGS_DIR)
    elif not payment_module.LIVE.value:
        test_or_live = 'TEST MODE'
    else:
        test_or_live = 'Paysbuy Order Summary'  # Live mode.
    psb_front_data = request.POST
    front_resp_dict = {'test_or_live': test_or_live, 
                      'psb_front_data': psb_front_data,}
    return front_resp_dict

@csrf_exempt
def success(request):
    """
    The order has been succesfully processed.
    We clear out the cart but let the payment processing get called by psb_back_resp
    """
    try:
        # If we get a response from Paysbuy:
        front_resp_dict = psb_front_resp(request)
        test_or_live = front_resp_dict['test_or_live']
        psb_front_data = front_resp_dict['psb_front_data']
        invoice = psb_front_data['result'][2:]
        txn_num = psb_front_data['apCode']
        cost = psb_front_data['amt']
        if (psb_front_data['method'] == '06' 
            and psb_front_data['result'][:2] == '02'):
            pay_result_message = 'Your order will be shipped upon receipt of funds.'
        elif psb_front_data['result'][:2] == '00':
            pay_result_message = 'Your order has been successfuly processed.'
        else:
            pay_result_message = 'Your order has failed. Please contact Paysbuy.'
    
        order = Order.objects.get(id__iexact=invoice)
    
    # Added to track total sold for each product
        for item in order.orderitem_set.all():
            product = item.product
            product.total_sold += item.quantity
            if config_value('PRODUCT','TRACK_INVENTORY'):
                product.items_in_stock -= item.quantity
            product.save()

    # Clean up cart now, the rest of the order will be cleaned on psb_back_resp
        for cart in Cart.objects.filter(customer=order.contact):
            cart.empty()

        del request.session['orderID']
        context = RequestContext(request, {
        'order': order,
        'test_or_live': test_or_live,
        'invoice': invoice,
        'txn_num': txn_num,
        'cost': cost,
        'pay_result_message': pay_result_message,
        })
        return render_to_response('shop/checkout/paysbuy/success.html', context)
    except:
        # If there is no response from Paysbuy we treat it as an internal request.
        try:
            order = Order.objects.from_request(request)
        except Order.DoesNotExist:
            return bad_or_missing(request,
                                 _('Your order has already been processed.'))

        # Added to track total sold for each product
        for item in order.orderitem_set.all():
            product = item.product
            product.total_sold += item.quantity
            if config_value('PRODUCT','TRACK_INVENTORY'):
                product.items_in_stock -= item.quantity
            product.save()

        # Clean up cart now, the rest of the order will be cleaned on psb_back_resp
        for cart in Cart.objects.filter(customer=order.contact):
            cart.empty()

        del request.session['orderID']
        context = RequestContext(request, {'order': order})
        return render_to_response('shop/checkout/success.html', context)

success = never_cache(success)
