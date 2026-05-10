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
