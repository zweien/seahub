
class VerifyLinkInfo {

  constructor(object) {
    this.path = object.path;
    this.username = object.username;
    this.status = object.status;
    this.ctime = object.ctime;
    this.link = object.link;
    this.receivers = object.receivers;
  }
}

export default VerifyLinkInfo;