import wal_e.log_help as log_help

def test_nonexisting_socket(tmpdir):
    # Must not raise an exception, silently failing is preferred for
    # now.
    log_help.configure(syslog_address=tmpdir.join('bogus'))

def test_format_structured_info():
    zero = {}, ''
    one = {'hello':'world'}, 'hello=world'
    many = {'hello':'world', 'goodbye':'world'}, 'hello=world goodbye=world'

    for d, expect in [zero, one, many]:
        assert log_help.WalELogger._fmt_structured(d) == expect

def test_fmt_logline_simple():
    out = log_help.WalELogger.fmt_logline(
        'The message', 'The detail', 'The hint', {'structured-data': 'yes'})
    assert out == """MSG: The message
DETAIL: The detail
HINT: The hint
STRUCTURED: structured-data=yes"""

    # Try without structured data
    out = log_help.WalELogger.fmt_logline(
        'The message', 'The detail', 'The hint')
    assert out == """MSG: The message
DETAIL: The detail
HINT: The hint"""
