import regex


def _quote_meta(s):
    special_chars = frozenset("()[]{}?*+|^$\\.-#&~")
    escape = lambda c: r'\{}'.format(c) if c in special_chars else c
    sp = (escape(c) for c in s)
    return r''.join(sp)


def match(regexp):
    return regex.compile(regexp)


def literal(s):
    return match(_quote_meta(s))


def expression(*res):
    return match(r''.join(r.pattern for r in res))


def optional(*res):
    return match(r'{}?'.format(group(expression(*res)).pattern))


def repeated(*res):
    return match(r'{}+'.format(group(expression(*res)).pattern))


def group(*res):
    return match(r'(?:{})'.format(expression(*res).pattern))


def capture(*res):
    return match(r'({})'.format(expression(*res).pattern))


def anchored(*res):
    return match(r'^{}$'.format(expression(*res).pattern))


class ImageRegexps(object):
    ALPHA_NUMERIC_REGEXP = match(r'[a-z0-9]+')
    SEPARATOR_REGEXP = match(r'(?:[._]|__|[-]*)')
    NAME_COMPONENT_REGEXP = expression(
        ALPHA_NUMERIC_REGEXP,
        optional(repeated(SEPARATOR_REGEXP, ALPHA_NUMERIC_REGEXP))
    )
    HOSTNAME_COMPONENT_REGEXP = match(r'(?:[a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9])')
    HOSTNAME_REGEXP = expression(
        HOSTNAME_COMPONENT_REGEXP,
        optional(repeated(literal(r'.'), HOSTNAME_COMPONENT_REGEXP)),
        optional(literal(r':'), match(r'[0-9]+'))
    )
    ANCHORED_HOSTNAME_REGEXP = anchored(HOSTNAME_REGEXP)
    TAG_REGEXP = match(r'[\w][\w.-]{0,127}')
    ANCHORED_TAG_REGEXP = anchored(TAG_REGEXP)
    DIGEST_REGEXP = match(r'[A-Za-z][A-Za-z0-9]*(?:[-_+.][A-Za-z][A-Za-z0-9]*)*[:][[:xdigit:]]{32,}')
    ANCHORED_DIGEST_REGEXP = anchored(DIGEST_REGEXP)
    NAME_REGEXP = expression(
        optional(HOSTNAME_REGEXP, literal(r'/')),
        NAME_COMPONENT_REGEXP,
        optional(repeated(literal(r'/'), NAME_COMPONENT_REGEXP))
    )
    ANCHORED_NAME_REGEXP = anchored(
        optional(capture(HOSTNAME_REGEXP), literal(r'/')),
        capture(NAME_COMPONENT_REGEXP, optional(repeated(literal(r'/'), NAME_COMPONENT_REGEXP)))
    )
    REFERENCE_REGEXP = anchored(
        capture(NAME_REGEXP),
        optional(literal(r':'), capture(TAG_REGEXP)),
        optional(literal(r'@'), capture(DIGEST_REGEXP))
    )
    IDENTIFIER_REGEXP = match(r'([a-f0-9]{64})')
    ANCHORED_IDENTIFIER_REGEXP = anchored(IDENTIFIER_REGEXP)


class DigestRegexps(object):
    DIGEST_REGEXP = match(r'[a-zA-Z0-9-_+.]+:[a-fA-F0-9]+')
    DIGEST_REGEXP_ANCHORED = anchored(DIGEST_REGEXP)
