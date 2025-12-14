INSERT INTO users (username, password_hash)
VALUES (
'admin',
''
) ON DUPLICATE KEY UPDATE username=username;

DELETE FROM users WHERE username='admin';

INSERT INTO users (username, password_hash)
VALUES (
'mateo',
''
) ON DUPLICATE KEY UPDATE username=username;


INSERT INTO users2 (username, password)
VALUES (
'admin',
'admin123'
) ON DUPLICATE KEY UPDATE username=username;

INSERT INTO users2 (username, password)
VALUES (
'test',
'admin123'
) ON DUPLICATE KEY UPDATE username=username;
