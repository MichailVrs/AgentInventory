FROM  registry.red-soft.ru/ubi8/ubi:8.0.2-260414
RUN dnf install -y --setopt=install_weak_deps=False osquery && \
    dnf clean all && \
    rm -rf /var/cache/dnf /var/log/dnf.log /var/log/hawkey.log
ENTRYPOINT [ "osqueryd" ]