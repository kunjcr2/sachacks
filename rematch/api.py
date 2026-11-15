"""One local API. Demo credentials are principal-bound, not production authentication."""
from contextlib import asynccontextmanager
import secrets
import time
import hmac
import json
import uuid
from fastapi import FastAPI, APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from rematch.common.config import ROOT, KEYS, ALLOWED_ORIGINS, COOKIE_SECURE, initialize_credentials, register_principal
from rematch.common.schemas import Onboard, PermissionUpdate, DiscussionUpdate, IntroductionAuthorization, Followup, ListingRequest, ClockAdvance, DemoSession
from rematch.service import Service, RuleError
from rematch.seed import seed, offline_spec
from rematch.extraction.sources import synthetic_source, public_source
from rematch.extraction.llm import LLMExtractor

def create_app(service=None, auth=None):
    service = service or Service()

    @asynccontextmanager
    async def lifespan(app):
        if auth is None:
            initialize_credentials()
        seed(service)
        service.process_outbox()
        yield
        service.store.engine.dispose()

    app = FastAPI(title='ReMatch central synthetic demo', lifespan=lifespan)
    app.state.service = service
    routes = APIRouter()
    sessions = {}

    @app.middleware('http')
    async def prevent_private_response_caching(request, call_next):
        response = await call_next(request)
        if not request.url.path.startswith('/assets/'):
            response.headers['Cache-Control'] = 'private, no-store'
            response.headers['CDN-Cache-Control'] = 'no-store'
            response.headers['Vercel-CDN-Cache-Control'] = 'no-store'
            vary = response.headers.get('Vary', '')
            if 'cookie' not in {item.strip().lower() for item in vary.split(',')}:
                response.headers['Vary'] = ', '.join(filter(None, [vary, 'Cookie']))
        return response

    def browser_intent(request):
        origin = request.headers.get('origin')
        allowed = not origin or origin.rstrip('/') in ALLOWED_ORIGINS or origin.rstrip('/') == f"{request.url.scheme}://{request.headers.get('host')}"
        if request.headers.get('X-Rematch-Intent') != 'browser' or not allowed:
            raise HTTPException(403, 'Browser origin is not allowed. Configure REMATCH_ALLOWED_ORIGINS with the exact frontend URL.')

    def set_session(actor, response):
        now = time.monotonic()
        for old, (_, expiry) in list(sessions.items()):
            if expiry <= now:
                sessions.pop(old, None)
        opaque = secrets.token_urlsafe(32)
        sessions[opaque] = (actor, now + 7200)
        response.set_cookie('rematch_demo', opaque, httponly=True, secure=COOKIE_SECURE, samesite='strict', max_age=7200, path='/')

    def principal(request: Request, x_api_key: str = Header(default='')):
        if not x_api_key:
            session = sessions.get(request.cookies.get('rematch_demo'))
            if session and session[1] > time.monotonic():
                if request.method not in {'GET', 'HEAD'}:
                    browser_intent(request)
                return session[0]
        configured = auth if auth is not None else json.loads((KEYS / 'central-auth.json').read_text())
        for actor, token in configured.items():
            if hmac.compare_digest(x_api_key, token):
                return actor
        raise HTTPException(401, 'Valid principal-bound demo credential required')

    def role(prefix):
        def check(actor=Depends(principal)):
            if not actor.startswith(prefix):
                raise HTTPException(403, 'This workspace is not available to this role')
            return actor
        return check

    patient = role('patient-')
    doctor = role('doctor-')
    team = role('team-')

    @app.exception_handler(RuleError)
    async def rules(request, exc):
        return JSONResponse(status_code=409, content={'detail': str(exc)})

    @routes.get('/health')
    def health():
        return {'status': 'ok', 'architecture': 'central-v1', 'synthetic_only': True}

    @routes.post('/demo/session')
    def choose_demo_account(body: DemoSession, request: Request, response: Response):
        browser_intent(request)
        fixed = {'patient-1', 'patient-2', 'doctor-1', 'team-1', 'team-2', 'onboarding'}
        created_patient = body.actor.startswith('patient-') and service.store.get('patient', body.actor)
        if body.actor not in fixed and not created_patient:
            raise HTTPException(404, 'Demo account not found')
        set_session(body.actor, response)
        return {'actor': body.actor, 'simulation': True}

    @routes.get('/demo/session')
    def current_demo_account(actor=Depends(principal)):
        return {'actor': actor, 'simulation': True}

    @routes.post('/profiles')
    def onboard(body: Onboard, request: Request, response: Response, actor=Depends(principal)):
        if actor != 'onboarding':
            raise HTTPException(403, 'Use the demo onboarding credential')
        pid = service.onboard(body.model_dump())
        token = register_principal(pid) if auth is None else uuid.uuid4().hex
        if auth is not None:
            auth[pid] = token
        if request.cookies.get('rematch_demo') and not request.headers.get('x-api-key'):
            set_session(pid, response)
            return {'patient_id': pid}
        return {'patient_id': pid, 'demo_token': token}

    @routes.get('/me')
    def profile(actor=Depends(patient)):
        return service.profile(actor)

    @routes.get('/me/clinical-summary')
    def clinical_summary(actor=Depends(patient)):
        return service.clinical_summary(actor)

    @routes.post('/me/permissions')
    def permission(body: PermissionUpdate, actor=Depends(patient)):
        return service.permission(actor, body.kind, body.granted)

    @routes.post('/me/records/connect')
    def connect(actor=Depends(patient)):
        return service.import_records(actor)

    @routes.post('/me/records/followup')
    def followup_record(actor=Depends(patient)):
        return service.import_records(actor, followup=True)

    @routes.delete('/me/records')
    def delete(actor=Depends(patient)):
        return service.delete_records(actor)

    @routes.post('/me/studies/{listing_id}/preview')
    def preview(listing_id: str, actor=Depends(patient)):
        return service.preview(actor, listing_id)

    @routes.post('/me/introductions')
    def authorize(body: IntroductionAuthorization, actor=Depends(patient)):
        return service.authorize(actor, body.preview_id, body.confirmed)

    @routes.post('/me/introductions/{intro_id}/withdraw')
    def withdraw(intro_id: str, actor=Depends(patient)):
        return service.withdraw_introduction(actor, intro_id)

    @routes.get('/doctor/discussions')
    def queue(actor=Depends(doctor)):
        return service.doctor_queue(actor)

    @routes.post('/doctor/discussions/{discussion_id}')
    def discuss(discussion_id: str, body: DiscussionUpdate, actor=Depends(doctor)):
        return service.discuss(actor, discussion_id, body.outcome, body.note)

    @routes.get('/team/listings')
    def listings(actor=Depends(team)):
        return [row | service.public_listing(row) | {'receipt': service.store.get('payment', row['id']) if row['status'] != 'draft' else None}
                for row in service.store.all('listing') if row['owner'] == actor]

    @routes.get('/team/sources')
    def sources(actor=Depends(team)):
        return service.store.all('source')

    @routes.post('/team/sources/{source_id}')
    def load_source(source_id: str, refresh: bool = False, actor=Depends(team)):
        try:
            source = synthetic_source(source_id) if source_id.startswith('SYN-') else public_source(source_id, refresh)
        except Exception:
            raise HTTPException(502, 'Source retrieval failed. Existing validated data was preserved.')
        service.update_source(source, actor)
        return source

    @routes.post('/team/listings')
    def listing(body: ListingRequest, actor=Depends(team)):
        source = service.store.get('source', body.source_id)
        if not source:
            raise HTTPException(404, 'Fetch a public source or choose a synthetic fixture first')
        try:
            spec = offline_spec(source) if body.mode == 'offline' else LLMExtractor().generate(source)
        except Exception as exc:
            # Never return SDK errors: they can contain request headers or credentials.
            service.audit('generation_failed', actor, source=source['id'], error_type=type(exc).__name__)
            raise HTTPException(502, 'Generation failed; no live success was recorded. Existing valid cached material was preserved. Check local model/key/network configuration.')
        service.store.put('extraction_attempt', source['id'] + ':' + actor, spec)
        if spec['state'] != 'VALIDATED_FOR_DEMO':
            return {'state': 'BLOCKED', 'errors': spec['errors'], 'execution': spec['execution']}
        row = service.publish(source, spec, actor)
        return {'state': 'PUBLISHED', 'listing_id': row['id'], 'execution': spec['execution']}

    @routes.get('/team/introductions')
    def introductions(actor=Depends(team)):
        return service.team_introductions(actor)

    @routes.post('/team/introductions/{intro_id}')
    def followup(intro_id: str, body: Followup, actor=Depends(team)):
        return service.followup(actor, intro_id, body.action)

    @routes.post('/demo/clock')
    def clock(body: ClockAdvance, actor=Depends(principal)):
        if actor != 'admin':
            raise HTTPException(403, 'Demo administrator credential required')
        return service.advance(body.days)

    # Preserve the authenticated Python/CLI contracts and expose a same-origin
    # browser prefix. Static assets never contain service keys.
    app.include_router(routes)
    app.include_router(routes, prefix='/api', include_in_schema=False)
    frontend = ROOT / 'frontend' / 'dist'
    if frontend.is_dir():
        app.mount('/', StaticFiles(directory=frontend, html=True), name='frontend')
    return app
