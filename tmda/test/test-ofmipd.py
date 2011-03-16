import unittest
import hmac
import md5

import lib.util
from lib.ofmipd import TestOfmipdServer

class FileAuthServer(TestOfmipdServer):
    def __init__(self):
        TestOfmipdServer.__init__(self)
        self.addFileAuth()
        #self.debug()

class ServerClientMixin(object):
    def setUp(self):
        self.serverSetUp()
        self.clientSetUp()

    def tearDown(self):
        self.server.stop()

    def serverSetUp(self):
        self.server = FileAuthServer()
        self.server.start()

    def clientSetUp(self):
        self.client = self.server.makeClient()
        self.client.connect(start_tls=True)

class ServerResponseTestMixin(ServerClientMixin):
    def setUp(self):
        ServerClientMixin.setUp(self)

        (code, lines) = self.client.exchange('EHLO test.com\r\n')
        self.ehloCode = code
        self.ehloLines = lines

    def checkExtensions(self, extensions):
        raise NotImplementedError()

    def checkAuthTypes(self, authTypes):
        raise NotImplementedError()

    def testExtensions(self):
        self.failUnless(self.ehloCode == 250)
        extensions = []
        authTypes = []
        for line in self.ehloLines[1:]:
            if line.startswith('AUTH '):
                authTypes.extend(line.split()[1:])

            parts = line.split(' ', 1)
            extensions.append(parts[0])

        self.checkExtensions(extensions)
        self.checkAuthTypes(authTypes)

    def testStartTls(self):
        (code, lines) = self.client.exchange('STARTTLS\r\n')
        self.failUnless(code == self.expectedStartTlsCode)

    def testAuth(self):
        (code, lines) = self.client.exchange('AUTH LOGIN\r\n')
        self.failUnless(code == self.expectedAuthCode)

class UnencryptedServerResponses(ServerResponseTestMixin, unittest.TestCase):
    expectedStartTlsCode = 502
    expectedAuthCode = 334

    def checkExtensions(self, extensions):
        self.failUnless(extensions == ['AUTH'])

    def checkAuthTypes(self, authTypes):
        self.failUnless(set(authTypes) == set(['LOGIN', 'PLAIN', 'CRAM-MD5']))

class SslServerResponses(ServerResponseTestMixin, unittest.TestCase):
    expectedStartTlsCode = 503
    expectedAuthCode = 334

    def serverSetUp(self):
        self.server = FileAuthServer()
        self.server.ssl()
        self.server.start()

    def checkExtensions(self, extensions):
        self.failUnless(extensions == ['AUTH'])

    def checkAuthTypes(self, authTypes):
        self.failUnless(set(authTypes) == set(['LOGIN', 'PLAIN', 'CRAM-MD5']))

class PreStartTlsServerResponses(ServerResponseTestMixin, unittest.TestCase):
    expectedStartTlsCode = 220
    expectedAuthCode = 530

    def serverSetUp(self):
        self.server = FileAuthServer()
        self.server.tls('on')
        self.server.start()

    def clientSetUp(self):
        self.client = self.server.makeClient()
        self.client.connect(start_tls=False)

    def checkExtensions(self, extensions):
        self.failUnless(extensions == ['STARTTLS'])

    def checkAuthTypes(self, authTypes):
        self.failUnless(len(authTypes) == 0)

class PostStartTlsServerResponses(ServerResponseTestMixin, unittest.TestCase):
    expectedStartTlsCode = 503
    expectedAuthCode = 334

    def serverSetUp(self):
        self.server = FileAuthServer()
        self.server.tls('on')
        self.server.start()

    def checkExtensions(self, extensions):
        self.failUnless(extensions == ['AUTH'])

    def checkAuthTypes(self, authTypes):
        self.failUnless(set(authTypes) == set(['LOGIN', 'PLAIN', 'CRAM-MD5']))

class OptionalStartTlsServerResponses(ServerResponseTestMixin,
                                      unittest.TestCase):
    expectedStartTlsCode = 220
    expectedAuthCode = 334

    def serverSetUp(self):
        self.server = FileAuthServer()
        self.server.tls('optional')
        self.server.start()

    def clientSetUp(self):
        self.client = self.server.makeClient()
        self.client.connect(start_tls=False)

    def checkExtensions(self, extensions):
        self.failUnless(set(extensions) == set(['STARTTLS', 'AUTH']))

    def checkAuthTypes(self, authTypes):
        self.failUnless(set(authTypes) == set(['LOGIN', 'PLAIN', 'CRAM-MD5']))

class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.server = FileAuthServer()
        self.server.start()

        self.client = self.server.makeClient()
        self.client.connect()

    def tearDown(self):
        self.server.stop()

    def authPlain(self, username, password, expectedCode):
        authString = '\x00'.join([username, username, password])
        authString = authString.encode('base64')[:-1]
        (code, lines) = self.client.exchange('AUTH PLAIN %s\r\n' % authString)

        self.failUnless(code == expectedCode,
            'username: %r password: %r code: %d' % (username, password, code))

    def authLogin(self, username, password, firstCode, secondCode):
        userString = username.encode('base64')[:-1]
        passString = password.encode('base64')[:-1]

        (code, lines) = self.client.exchange('AUTH LOGIN %s\r\n' % userString)
        self.failUnless(code == firstCode)

        if firstCode == 334:
            (code, lines) = self.client.exchange('%s\r\n' % passString)
            self.failUnless(code == secondCode,
                'username: %r password: %r code: %d' % \
                (username, password, code))

    def authCramMd5(self, username, password, expectedCode):
        (code, lines) = self.client.exchange('AUTH CRAM-MD5\r\n')
        self.failUnless(code == 334)
        self.failUnless(len(lines) == 1)

        ticket = lines[0].decode('base64')
        digest = hmac.new(password, ticket, md5).hexdigest()
        message = '%s %s' % (username, digest)
        message = message.encode('base64')[:-1]

        (code, lines) = self.client.exchange('%s\r\n' % message)
        self.failUnless(code == expectedCode,
            'username: %r password: %r code: %d' % (username, password, code))

    def testPlain(self):
        self.authPlain('testuser', 'testpassword', 235)

    def testLogin(self):
        self.authLogin('testuser', 'testpassword', 334, 235)

    def testCramMd5(self):
        self.authCramMd5('testuser', 'testpassword', 235)

    _badUsernames = [
        'testuserr',
        'testuse',
        'testus',
        'testu',
        '\x00',
        '\x00testuser',
    ]
    _badPasswords = [
        'testpasswordd',
        'testpasswor',
        'testpasswo',
        'testpassw',
        'testpass',
        '',
        ' ',
        '\x00',
    ]

    def testPlainFailure(self):
        for password in self._badPasswords:
            self.authPlain('testuser', password, 535)

        for username in self._badUsernames:
            self.authPlain(username, 'testpassword', 535)

    def testLoginFailure(self):
        for password in self._badPasswords:
            # For LOGIN, an empty password is ignored. I don't know if this
            # is a bug or not, but it's probably how tmda-ofmipd has always
            # worked.
            if password == '':
                continue
            self.authLogin('testuser', password, 334, 535)

        for username in self._badUsernames:
            self.authLogin(username, 'testpassword', 334, 535)

    def testCramMd5Failure(self):
        for password in self._badPasswords:
            self.authCramMd5('testuser', password, 535)

        for username in self._badUsernames:
            self.authCramMd5(username, 'testpassword', 535)

class SendTestMixin(ServerClientMixin):
    def beginSend(self):
        (code, lines) = self.client.exchange('MAIL FROM: testuser@nowhere.com'
                                             '\r\n')
        self.failUnless(code == 250)

        (code, lines) = self.client.exchange('RCPT TO: fakeuser@fake.com\r\n')
        self.failUnless(code == 250)

        (code, lines) = self.client.exchange('DATA \r\n')
        self.failUnless(code == 354)

    def sendLine(self, line):
        self.client.send('%s\r\n' % line)

    def finishSend(self):
        (code, lines) = self.client.exchange('.\r\n')
        self.failUnless(code == 250)

    def testSend(self):
        self.client.signOn()
        self.beginSend()
        self.sendLine('X-nothing: nothing')
        self.sendLine('')
        self.sendLine('Shut up.')
        self.finishSend()

    def testSendFailure(self):
        (code, lines) = self.client.exchange('MAIL TO: testuser@nowhere.com'
                                             '\r\n')
        self.failUnless(code == 530)

class UnencryptedSendTest(SendTestMixin, unittest.TestCase):
    pass

class SslSendTest(SendTestMixin, unittest.TestCase):
    def serverSetUp(self):
        self.server = FileAuthServer()
        self.server.ssl()
        self.server.start()

class TlsSendTest(SendTestMixin, unittest.TestCase):
    def serverSetUp(self):
        self.server = FileAuthServer()
        self.server.tls('on')
        self.server.start()

# XXX Add tests:
# Dupes and syntax errors

if __name__ == '__main__':
    lib.util.fixupFiles()

    runner = unittest.TextTestRunner(verbosity=2)
    unittest.main(testRunner=runner)