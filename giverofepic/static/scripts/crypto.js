const crypto = require('crypto')

function get_crypto(secret, encode) {
  // Create hashed key from password/key
  let m = crypto.createHash('md5').update(secret)
  const key = m.digest('hex')
  m = crypto.createHash('md5').update(secret + key)
  const iv = m.digest('hex').slice(0, 16) // only in aes-256

  return encode
    ? crypto.createCipheriv('aes-256-cbc', key, iv)
    : crypto.createDecipheriv('aes-256-cbc', key, iv)
}

test_crypto_function()
function test_crypto_function() {
  const secret = 'f8abb29f13cb932704badb0de414ab08ca9f6c63' // crypto.randomBytes(20).toString('hex')

  const value = 'hello world'
  const data = Buffer.from(value, 'utf8').toString('binary')
  const cipher = get_crypto(secret, true)
  const encrypted = Buffer.concat([cipher.update(data, 'utf8'), cipher.final()]).toString('binary')
  const encoded = Buffer.from(encrypted, 'binary').toString('base64')
  console.log('encoded:', encoded)

  const edata = Buffer.from(encoded, 'base64').toString('binary')
  const decipher = get_crypto(secret, false)
  const decoded = Buffer.concat([decipher.update(edata, 'binary'), decipher.final()]).toString('utf-8')
  console.log('decoded:', decoded)
}