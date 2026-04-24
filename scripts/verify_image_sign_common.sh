#!/bin/bash
verify_image_sign_common() {
    image_file="${1}"
    cms_sig_file="sig.cms"
    TMP_DIR=$(mktemp -d)
    DATA_FILE="${2}"
    CMS_SIG_FILE="${3}"
    
    openssl version | awk '$2 ~ /(^0\.)|(^1\.(0\.|1\.0))/ { exit 1 }'
    if [ $? -eq 0 ]; then
        # for version 1.1.1 and later
        no_check_time="-no_check_time"
    else
        # for version older than 1.1.1 use noattr
        no_check_time="-noattr"
    fi
    
    EFI_CERTS_DIR=/tmp/efi_certs
    RESULT="CMS Verification Failure"

    # Verify the signature in two ways:
    # 1. As a complete certificate chain root of trust which requires the DB Key to be a self-signed root, but the image
    #    signed with an intermediate embedded into the certificate.
    # 2. Assuming the DB key directly signed the image without trusting the certificate embedded into the
    #    pkcs7 signature (-nointern). Since the DB key is trusted, it doesn't need to be a root CA so we turn off root
    #    CA verification with the -noverify flag.
    for variant in "-CAfile" "-nointern -noverify -certfile"; do
        LOG=$(openssl cms -verify $no_check_time -noout ${variant} $EFI_CERTS_DIR/cert.pem -binary -in ${CMS_SIG_FILE} -content ${DATA_FILE} -inform pem 2>&1 > /dev/null )
        VALIDATION_RES=$?
        if [ $VALIDATION_RES -eq 0 ]; then
            RESULT="CMS Verified OK"
            if  [ -d "${TMP_DIR}" ]; then rm -rf ${TMP_DIR}; fi
            echo "verification ok:$RESULT"
            # No need to continue.
            # Exit without error if any success signature verification.
            return 0
        fi
    done

    if  [ -d "${TMP_DIR}" ]; then rm -rf ${TMP_DIR}; fi
    return 1
}
