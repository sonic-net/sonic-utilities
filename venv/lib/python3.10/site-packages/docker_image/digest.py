from . import regexp

DigestRegexps = regexp.DigestRegexps


class InvalidDigest(Exception):
    @classmethod
    def default(cls):
        return cls("invalid digest")


class DigestUnsupported(InvalidDigest):
    @classmethod
    def default(cls):
        return cls("unsupported digest algorithm")


class DigestInvalidLength(InvalidDigest):
    @classmethod
    def default(cls):
        return cls("invalid checksum digest length")


DIGESTS_SIZE = {
    'sha256': 32,
    'sha384': 48,
    'sha512': 64,
}


def validate_digest(digest):
    matched = DigestRegexps.DIGEST_REGEXP_ANCHORED.match(digest)
    if not matched:
        raise InvalidDigest.default()

    i = digest.find(':')
    # case: "sha256:" with no hex.
    if i < 0 or ((i + 1) == len(digest)):
        raise InvalidDigest.default()

    algorithm = digest[:i]
    if algorithm not in DIGESTS_SIZE:
        raise DigestUnsupported.default()

    if DIGESTS_SIZE[algorithm] * 2 != len(digest[i + 1:]):
        raise DigestInvalidLength.default()
