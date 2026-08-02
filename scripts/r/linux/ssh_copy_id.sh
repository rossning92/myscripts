if [ ! -f ~/.ssh/id_rsa.pub ]; then
    echo 'No SSH key found. Generating new RSA key pair...'
    ssh-keygen -t rsa
fi

echo 'Copying SSH public key to remote server...'
ssh-copy-id -o StrictHostKeyChecking=no -p $SSH_PORT $SSH_USER@$SSH_HOST
