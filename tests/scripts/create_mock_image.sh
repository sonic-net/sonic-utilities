repo_dir=$1
input_image=$2
output_file=$3
cert_file=$4
key_file=$5
tmp_dir=
clean_up()
{
    sudo rm -rf $tmp_dir
    sudo rm -rf $output_file
    exit $1
}

DIR="$(dirname "$0")"

tmp_dir=$(mktemp -d)
sha1=$(cat $input_image | sha1sum | awk '{print $1}')
echo -n "."
cp $repo_dir/installer/sharch_body.sh $output_file || {
    echo "Error: Problems copying sharch_body.sh"
    clean_up 1
}
# Replace variables in the sharch template
sed -i -e "s/%%IMAGE_SHA1%%/$sha1/" $output_file
echo -n "."
tar_size="$(wc -c < "${input_image}")"
cat $input_image >> $output_file
sed -i -e "s|%%PAYLOAD_IMAGE_SIZE%%|${tar_size}|" ${output_file}
CMS_SIG="${tmp_dir}/signature.sig"

echo "$0 CMS signing ${input_image} with ${key_file}. Output file ${output_file}"
. $repo_dir/scripts/sign_image_dev.sh
sign_image_dev  ${cert_file} ${key_file} $output_file ${CMS_SIG} || clean_up 1
    
cat ${CMS_SIG} >> ${output_file}
echo "Signature done."
# append signature to binary
sudo rm -rf ${CMS_SIG}
sudo rm -rf $tmp_dir
exit 0
