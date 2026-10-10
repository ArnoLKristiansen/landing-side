"""Import record_usage in server-side Python applications; never send prompts or API keys."""
import hashlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from storage import import_events

def record_usage(response, program, function):
    """Call once after a non-streaming Responses or Chat Completions response.
    Use a stable response.id for deduplication. For streaming, call with the final usage-bearing object.
    """
    r=response.model_dump() if hasattr(response,'model_dump') else response
    u=r.get('usage')
    if not u: raise ValueError('Svaret indeholder ingen usage-oplysninger')
    identity=r.get('id')
    if not identity: raise ValueError('Et stabilt response-id er nødvendigt')
    ts=datetime.now(timezone.utc)
    inp=u.get('input_tokens',u.get('prompt_tokens',0)); out=u.get('output_tokens',u.get('completion_tokens',0))
    details=u.get('input_tokens_details') or u.get('prompt_tokens_details') or {}
    task='tracked:'+hashlib.sha256((program+'\0'+function).encode()).hexdigest()
    return import_events({'events':[{'id':'api:'+hashlib.sha256(identity.encode()).hexdigest(),'source':'api_tracked',
      'timestamp':ts.isoformat(),'day':ts.astimezone(ZoneInfo('Europe/Copenhagen')).date().isoformat(),
      'task':task,'program':program,'function':function,'model':r.get('model','Ukendt model'),
      'input':inp,'cached':details.get('cached_tokens',0),'output':out}]})
