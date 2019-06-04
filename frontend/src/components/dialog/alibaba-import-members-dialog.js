import React from 'react';
import PropTypes from 'prop-types';
import { gettext } from '../../utils/constants';
import { Button, Modal, ModalHeader, ModalBody, ModalFooter, Label, Input, Alert } from 'reactstrap';
import { seafileAPI } from '../../utils/seafile-api.js';
import '../../css/manage-members-dialog.css';

var FormData = require('form-data');
const propTypes = {
  groupID: PropTypes.string.isRequired,
  toggleImportMembersDialog: PropTypes.func.isRequired,
  onGroupChanged: PropTypes.func.isRequired,
  isOwner: PropTypes.bool,
};

class ImportMembersDialog extends React.Component {

  constructor(props) {
    super(props);
    this.state = {
      selectedOption: null,
      errMessage: [],
      isItemFreezed: false,
      failedMsg: [],
      successMsg: '',
      uploadfilename: '',
    };
  }

  toggle = () => {
    this.props.toggleImportMembersDialog();
  }

  handleSubmit = () => {
    let isZHCN = window.app.config.lang === 'zh-cn';
    let tmp = document.querySelector('#inputFile');
    let file = tmp.files[0];
    let formData = new FormData();
    formData.append('file', file);
    const url = window.app.config.serviceURL + '/alibaba/api/groups/' + this.props.groupID +  '/members/import/';

    seafileAPI._sendPostRequest(url, formData).then((res) => {
      let failedMsg = [];
      for(let i = 0; i < res.data.failed.length; i++) {
        failedMsg.push(res.data.failed[i].email + ': ' + res.data.failed[i].error_msg);
      }

      let successMsg = '';
      if (res.data.success.length > 0){
        if(isZHCN){
          successMsg = '成功导入' + res.data.success.length + '个成员!';
        }else{
          successMsg = 'Successfully imported ' + res.data.success.length + ' members!';
        }
      }
      this.setState({
        successMsg: successMsg,
        failedMsg: failedMsg,
      });

    }).catch((error) => {
    });
  }

  handleChangeFile = (e) => {
    let file = document.querySelector('#inputFile').files[0];
    this.setState({
      uploadfilename:file.name,
    });
  }

  render() {
    if (window.app.config.lang === 'zh-cn'){
      return (
        <Modal isOpen={true} toggle={this.toggle}>
          <ModalHeader toggle={this.toggle}>{'从.csv文件批量导入文件'}</ModalHeader>
          <ModalBody>
            <Label htmlFor="inputFile" className="primary" style={{borderStyle:'solid', borderWidth:'0.5px', borderRadius:'2px', padding:'3px 8px', cursor: 'pointer'}}>{'上传文件'}</Label>
            <input id="inputFile" style={{visibility:'hidden', display:'none'}} type="file" onChange={this.handleChangeFile}/>
            {this.state.uploadfilename.length > 0 &&
              <span >{'  ' + this.state.uploadfilename}</span>
            }
            <p className="tip">说明：将团队成员工号写入.csv纯文本文件，每行一个工号<br/>例子：<br/>101012<br/>012345<br/>101011<br/>000311<br/>......</p>
            <Button color="secondary" onClick={this.handleSubmit}>{'提交'}</Button>
            {this.state.successMsg &&
              <Alert color='info'>{this.state.successMsg}</Alert>
            }
            {this.state.failedMsg.length > 0 &&
              this.state.failedMsg.map((item, index = 0) => {
                return (
                  <Alert key={index} color="danger">{item}</Alert>
                );
              })
            }
          </ModalBody>
          <ModalFooter>
            <Button color="secondary" onClick={this.toggle}>{gettext('关闭')}</Button>
          </ModalFooter>
        </Modal>
      );
    } else {
      return (
        <Modal isOpen={true} toggle={this.toggle}>
          <ModalHeader toggle={this.toggle}>{'Import group members in batch via a .csv file'}</ModalHeader>
          <ModalBody>
            <Label htmlFor="inputFile" className="primary" style={{borderStyle:'solid', borderWidth:'0.5px', borderRadius:'2px', padding:'3px 8px', cursor: 'pointer'}}>{'Upload Files'}</Label>
            <input id="inputFile" style={{visibility:'hidden', display:'none'}} type="file" onChange={this.handleChangeFile}/>
            {this.state.uploadfilename.length > 0 &&
              <span >{'  ' + this.state.uploadfilename}</span>
            }
            <p className="tip">Note: Take your team members' employee ID, and keep one ID each line<br/>Example:<br/>101012<br/>012345<br/>101011<br/>000311<br/>......</p>
            <Button color="secondary" onClick={this.handleSubmit}>{'Submit'}</Button>
            {this.state.successMsg &&
              <Alert color='info'>{this.state.successMsg}</Alert>
            }
            {this.state.failedMsg.length > 0 &&
              this.state.failedMsg.map((item, index = 0) => {
                return (
                  <Alert key={index} color="danger">{item}</Alert>
                );
              })
            }
          </ModalBody>
          <ModalFooter>
            <Button color="secondary" onClick={this.toggle}>{gettext('Close')}</Button>
          </ModalFooter>
        </Modal>
      );
    }
  }
}

ImportMembersDialog.propTypes = propTypes;

export default ImportMembersDialog;
