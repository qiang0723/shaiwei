# TS-v5-R3C 镜像身份转录补遗

日期：2026-08-13（UTC+8）

第一次加固后镜像使用了正确提交短前缀`3b85077`，但手工传入的40位
`SHAIWEI_RELEASE_GIT_HEAD=3b8507762b8b7b9ff936d493f7c6fbb4783a6c5b`与真实HEAD
`3b8507708854bed6da8418508275f1786612b594`不一致。该镜像只运行过`network=none`、无release、无secret
的preflight/audit和一次哨兵拒绝；API调用、费用和研究结果均为0。

错误镜像内容ID`sha256:dc70615b8067418d499313efb621720c3b0e8e43f5994be6e6c5c84d2a069278`
永久记为provisional，不得写入execution release或执行真实调用。后续终版镜像必须使用`git rev-parse
HEAD`完整输出自动传入并核对镜像环境、manifest代码快照、内容ID和origin/main；旧镜像不删除以保留
本机证据，不能冒充终版。

终版以真实`git rev-parse HEAD`输出`9ba7b52bf005dd3e7d0f1c48f398f884a74c9caf`重建；镜像内容ID为
`sha256:0c07a2eb7142c6e9f4fed8ab7b85b695aac561245325b8b0417ec61efe38b92a`，镜像内权威函数返回Git
HEAD完全一致，代码快照为`227c299691427566080a2204fbb284cdbf4687a6a655bb8ec93771deb2c1695b`。
该镜像再次通过断网、只读、非root、无secret preflight和独立audit，可用于后续结果前release绑定。
