from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def login_admin():
    res = client.post('/api/auth/login', json={'email': 'admin@test.com', 'password': 'Admin@12345'})
    assert res.status_code == 200
    return {'Authorization': 'Bearer ' + res.json()['access_token']}


def test_admin_can_list_users():
    headers = login_admin()
    res = client.get('/api/admin/users', headers=headers)
    assert res.status_code == 200
    assert any(u['email'] == 'admin@test.com' for u in res.json()['users'])


def test_temp_password_flow():
    headers = login_admin()
    email = 'auth-flow-member@test.com'
    client.delete(f'/api/admin/users/{email}', headers=headers)
    created = client.post('/api/admin/users', headers=headers, json={
        'email': email,
        'temp_password': 'Temp@12345',
        'role': 'researcher',
        'name': 'Auth Flow Member'
    })
    assert created.status_code == 200
    challenge = client.post('/api/auth/login', json={'email': email, 'password': 'Temp@12345'})
    assert challenge.status_code == 200
    assert challenge.json()['challenge'] == 'NEW_PASSWORD_REQUIRED'
    changed = client.post('/api/auth/new-password', json={
        'email': email,
        'session': challenge.json()['session'],
        'new_password': 'NewPass@12345'
    })
    assert changed.status_code == 200
    assert changed.json()['user']['status'] == 'CONFIRMED'


def test_local_forgot_password_flow():
    headers = login_admin()
    email = 'forgot-member@test.com'
    client.delete(f'/api/admin/users/{email}', headers=headers)
    created = client.post('/api/admin/users', headers=headers, json={
        'email': email,
        'temp_password': 'Temp@12345',
        'role': 'researcher',
        'name': 'Forgot Flow Member'
    })
    assert created.status_code == 200
    # Activate the user once so the reset path represents a normal account.
    challenge = client.post('/api/auth/login', json={'email': email, 'password': 'Temp@12345'}).json()
    changed = client.post('/api/auth/new-password', json={
        'email': email,
        'session': challenge['session'],
        'new_password': 'OldPass@12345'
    })
    assert changed.status_code == 200

    started = client.post('/api/auth/forgot-password', json={'email': email})
    assert started.status_code == 200
    reset_code = started.json().get('reset_code')
    assert reset_code
    confirmed = client.post('/api/auth/confirm-forgot-password', json={
        'email': email,
        'confirmation_code': reset_code,
        'new_password': 'ResetPass@12345'
    })
    assert confirmed.status_code == 200
    logged_in = client.post('/api/auth/login', json={'email': email, 'password': 'ResetPass@12345'})
    assert logged_in.status_code == 200
    assert logged_in.json()['user']['status'] == 'CONFIRMED'
