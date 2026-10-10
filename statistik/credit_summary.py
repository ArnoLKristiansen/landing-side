from decimal import Decimal, InvalidOperation

def credit_summary(limits, purchase):
    result={'remaining':None,'used':None,'purchased':purchase.get('credits'),
      'observed_at':limits.get('observed_at'),'unlimited':limits.get('credits_unlimited',False)}
    if result['unlimited']:return result
    try:
        remaining=Decimal(str(limits.get('credits')))
        if not remaining.is_finite() or remaining<0:return result
        result['remaining']=str(remaining)
        purchased=Decimal(str(purchase.get('credits')))
        # A larger balance may mean a new top-up. Never invent negative usage.
        if purchased.is_finite() and purchased>=remaining:
            result['used']=str(purchased-remaining)
    except InvalidOperation:pass
    return result
