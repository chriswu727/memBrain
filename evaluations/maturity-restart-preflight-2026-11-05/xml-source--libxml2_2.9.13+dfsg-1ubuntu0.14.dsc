-----BEGIN PGP SIGNED MESSAGE-----
Hash: SHA512

Format: 3.0 (quilt)
Source: libxml2
Binary: libxml2, libxml2-utils, libxml2-dev, libxml2-doc, python3-libxml2
Architecture: any all
Version: 2.9.13+dfsg-1ubuntu0.14
Maintainer: Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>
Uploaders:  Aron Xu <aron@debian.org>, YunQiang Su <wzssyqa@gmail.com>,
Homepage: http://xmlsoft.org
Description: GNOME XML library
 XML is a metalanguage to let you design your own markup language.
 A regular markup language defines a way to describe information in
 a certain class of documents (eg HTML). XML lets you define your
 own customized markup languages for many classes of document. It
 can do this because it's written in SGML, the international standard
 metalanguage for markup languages.
Standards-Version: 4.6.0
Vcs-Browser: https://salsa.debian.org/xml-sgml-team/libxml2
Vcs-Git: https://salsa.debian.org/xml-sgml-team/libxml2.git
Testsuite: autopkgtest
Testsuite-Triggers: build-essential, pkg-config
Build-Depends: debhelper-compat (= 13)
Build-Depends-Arch: dh-sequence-python3 <!nopython>, libicu-dev, liblzma-dev, libpython3-all-dev <!nopython>, pkg-config, python3-all-dev:any (>= 3.5) <!nopython>, rename, zlib1g-dev | libz-dev
Build-Depends-Indep: pkg-config
Package-List:
 libxml2 deb libs optional arch=any
 libxml2-dev deb libdevel optional arch=any
 libxml2-doc deb doc optional arch=all
 libxml2-utils deb text optional arch=any
 python3-libxml2 deb python optional arch=any profile=!nopython
Checksums-Sha1:
 67f5969e6bd8ba13ec13fa2d01686249088a9c8e 2351356 libxml2_2.9.13+dfsg.orig.tar.xz
 7c5547c3ee23c33c64e20375890eb99859722c7f 63012 libxml2_2.9.13+dfsg-1ubuntu0.14.debian.tar.xz
Checksums-Sha256:
 13cf2e55e603c34143486f4082cbf202859ac1eec5130b8d8e5e3c06a9902d8a 2351356 libxml2_2.9.13+dfsg.orig.tar.xz
 25ff38d4356a491aa49c415cff6460453793694a72e4c9a894b94128e65b8040 63012 libxml2_2.9.13+dfsg-1ubuntu0.14.debian.tar.xz
Files:
 6ef8e527d14a35d1c9721cb1c5061ab4 2351356 libxml2_2.9.13+dfsg.orig.tar.xz
 75e6bbc149ff6487bd0a5129d7e989f4 63012 libxml2_2.9.13+dfsg-1ubuntu0.14.debian.tar.xz
Original-Maintainer: Debian XML/SGML Group <debian-xml-sgml-pkgs@lists.alioth.debian.org>

-----BEGIN PGP SIGNATURE-----

iQJSBAEBCgA8FiEEtNElVmlvlJD9Tt9SD2QDvITYlW8FAmrFXwYeHGNoYXJsZXMu
Y29jaHJhbkBjYW5vbmljYWwuY29tAAoJEA9kA7yE2JVvuRkP/37+pkCrp6Qv6m3m
mezgAHG9wowFA9ghy7iPErPhchUQcUEuvhmRI2M3DsApOrrwZMacxpB6spj+dQ7e
W3+LedVGc8epER3gWNqiizpxle0H8WwbJDL0CgRTc+w5DINDI6BmJkOTNF6sSDnO
ZTguhMk2AYV2rqM4deSAFI0ym0ZrB7bWNAVEY5cupK+F28bpH9+QZ/AVvQSLTmsW
3AUfR1gw/+jdy+XcyZddJidn0IEwM2dgbmd0H1JbNmmt40dfhyIoKWaxI1rh1+55
zF54auOkuoARB4n6lL7uY8HX9Q7Jipe+bLJbT6cPAFTEnidtUND2n2KqSFkjaH57
Bb0QJ64p90nlDjBlsCnqfwkjSJkY28nKDWn/Q+H3odYuFOfPosMTGxifLnv4X3ti
v8GmMLb8zkI6Igv64ma05XltyjK6MoejL1QzCt9eUlebdye9+Lurk5R9+P8HckiL
aZatPvQ1pUtfHoxwdp0X5/jZ1MIFqJd+ym5Er+bJmN+APYgkR7QVsYWgW4EMLDzS
/dhcyRdY2tST6Z6FLE6Vg6TJ7LtH6B7dNMS/nDR023rg6e5Y5WAPcRtElnLz1ow9
J2wIZDx3BnyKutm4xrPO4c35wfTuqQG2/M3lq7E238bNH1ozi1AeWtZak+cZxR/Y
4zsj7VopMgPpWMmc7ghnQl3svXCM
=mqZN
-----END PGP SIGNATURE-----
