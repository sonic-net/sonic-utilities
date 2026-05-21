repo_dir=$1
out_dir=$2
mock_image="mock_img.bin"
output_file=$out_dir/output_file.bin
cert_file=$3
other_cert_file=$4
tmp_dir=
clean_up()
{
    sudo rm -rf $tmp_dir
    sudo rm -rf $mock_image
    exit $1
}
DIR="$(dirname "$0")"
[ -d $out_dir ] || rm -rf $out_dir
mkdir $out_dir
tmp_dir=$(mktemp -d)
#generate self signed keys and certificate
key_file=$tmp_dir/private-key.pem
pub_key_file=$tmp_dir/public-key.pem
openssl ecparam -name secp256r1 -genkey -noout -out $key_file
openssl ec -in $key_file -pubout -out $pub_key_file
openssl req -new -x509 -key $key_file -out $cert_file -days 360 -subj "/C=US/ST=Test/L=Test/O=Test/CN=Test"
alt_key_file=$tmp_dir/alt-private-key.pem
alt_pub_key_file=$tmp_dir/alt-public-key.pem
openssl ecparam -name secp256r1 -genkey -noout -out $alt_key_file
openssl ec -in $alt_key_file -pubout -out $alt_pub_key_file
openssl req -new -x509 -key $alt_key_file -out $other_cert_file -days 360 -subj "/C=US/ST=Test/L=Test/O=Test/CN=Test"

echo "this is a mock image\nThis is another line !2#4%6\n" > $mock_image
echo "Created a mock image with following text:"
cat $mock_image
# create signed mock image

sh $DIR/create_mock_image.sh $repo_dir $mock_image $output_file $cert_file $key_file || {
    echo "Error: unable to create mock image"   
    clean_up 1
}

[ -f "$output_file" ] || {
    echo "signed mock image not created - exiting without testing"
    clean_up 1
}

test_image_1=$out_dir/test_image_1.bin
cp -v $output_file $test_image_1 || {
    echo "Error: Problems copying image"
    clean_up 1
}

# test_image_1 = modified image size to something else - should fail on signature verification
image_size=$(sed -n 's/^payload_image_size=\(.*\)/\1/p' < $test_image_1)
sed -i "/payload_image_size=/c\payload_image_size=$(($image_size - 5))" $test_image_1

test_image_2=$out_dir/test_image_2.bin
cp -v $output_file $test_image_2 || {
    echo "Error: Problems copying image"
    clean_up 1
}

# test_image_2 = modified image sha1 to other sha1 value - should fail on signature verification
im_sha=$(sed -n 's/^payload_sha1=\(.*\)/\1/p' < $test_image_2)
sed -i "/payload_sha1=/c\payload_sha1=2f1bbd5a0d411253103e688e4e66c00c94bedd40" $test_image_2

tmp_image=$tmp_dir/"tmp_image.bin"
echo "this is a different image now" >> $mock_image
sh $DIR/create_mock_image.sh $repo_dir $mock_image $tmp_image $cert_file $key_file || {
    echo "Error: unable to create mock image"   
    clean_up 1
}
# test_image_3 = original mock image with wrong signature
# Extract cms signature from signed file
test_image_3=$out_dir/"test_image_3.bin"
tmp_sig="${tmp_dir}/tmp_sig.sig"
TMP_TAR_SIZE=$(head -n 50 $tmp_image | grep "payload_image_size=" | cut -d"=" -f2- )
sed -e '1,/^exit_marker$/d' $tmp_image | tail -c +$(( $TMP_TAR_SIZE + 1 )) > $tmp_sig

TAR_SIZE=$(head -n 50 $output_file | grep "payload_image_size=" | cut -d"=" -f2- )
SHARCH_SIZE=$(sed '/^exit_marker$/q' $output_file | wc -c)
SIG_PAYLOAD_SIZE=$(($TAR_SIZE + $SHARCH_SIZE ))
head -c $SIG_PAYLOAD_SIZE $output_file > $test_image_3
sudo rm -rf $tmp_image

cat ${tmp_sig} >> ${test_image_3}

# test_image_4 = modified image with original mock image signature
test_image_4=$out_dir/"test_image_4.bin"
head -c $SIG_PAYLOAD_SIZE $output_file > $test_image_4
echo "this is additional line" >> $test_image_4
cat ${tmp_sig} >> ${test_image_4}
clean_up 0