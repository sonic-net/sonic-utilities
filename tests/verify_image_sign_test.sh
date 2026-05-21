#!/bin/bash
image_file="${1}"
cert_path="${2}"
cms_sig_file="sig.cms"
TMP_DIR=$(mktemp -d)
DATA_FILE="${TMP_DIR}/data.bin"
CMS_SIG_FILE="${TMP_DIR}/${cms_sig_file}"
lines_for_lookup=50

TAR_SIZE=$(head -n $lines_for_lookup $image_file | grep "payload_image_size=" | cut -d"=" -f2- )
SHARCH_SIZE=$(sed '/^exit_marker$/q' $image_file | wc -c)
SIG_PAYLOAD_SIZE=$(($TAR_SIZE + $SHARCH_SIZE ))
# Extract cms signature from signed file - exit marker marks last sharch prefix + number of image lines + 1 for next linel
# Add extra byte for payload - extracting image signature from line after data file
sed -e '1,/^exit_marker$/d' $image_file | tail -c +$(( $TAR_SIZE + 1 )) > $CMS_SIG_FILE
# Extract image from signed file
head -c $SIG_PAYLOAD_SIZE $image_file > $DATA_FILE
EFI_CERTS_DIR=/tmp/efi_certs
[ -d $EFI_CERTS_DIR ] && rm  -rf $EFI_CERTS_DIR
mkdir $EFI_CERTS_DIR
cp $cert_path $EFI_CERTS_DIR/cert.pem

DIR="$(dirname "$0")"
. $DIR/verify_image_sign_common.sh
verify_image_sign_common $image_file $DATA_FILE $CMS_SIG_FILE
VERIFICATION_RES=$?
if  [ -d "${TMP_DIR}" ]; then rm -rf ${TMP_DIR}; fi
[ -d $EFI_CERTS_DIR ] && rm  -rf $EFI_CERTS_DIR
exit $VERIFICATION_RES