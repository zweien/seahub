import React, { Fragment } from 'react';
import PropTypes from 'prop-types';
import {gettext, isPro, siteRoot, serviceURL, username} from '../../utils/constants';
import { Input } from 'reactstrap';
import { Button } from 'reactstrap';
import { seafileAPI } from '../../utils/seafile-api.js';
import { Utils } from '../../utils/utils';
import toaster from '../toast';
import SharePermissionEditor from '../select-editor/share-permission-editor';
import '../../css/invitations.css';

class ShareItem extends React.Component {

  constructor(props) {
    super(props);
    this.state = {
      isOperationShow: false
    };
  }
  
  onMouseEnter = () => {
    this.setState({isOperationShow: true});
  }

  onMouseLeave = () => {
    this.setState({isOperationShow: false});
  }

  deleteShareItem = () => {
    let item = this.props.item;
    this.props.deleteShareItem(item.shared_secret, item.to_sever_url);
  }

  render() {
    let item = this.props.item;
    return (
      <tr onMouseEnter={this.onMouseEnter} onMouseLeave={this.onMouseLeave}>
        <td className="name">{item.to_user}</td>
        <td>{item.to_sever_url}</td>
        <td>{item.permission}</td>
        {/* <td>
          <SharePermissionEditor 
            isTextMode={true}
            isEditIconShow={this.state.isOperationShow}
            currentPermission={currentPermission}
            permissions={this.props.permissions}
            onPermissionChanged={this.onChangeUserPermission}
          />
        </td> */}
        <td>
          <span
            className={`sf2-icon-x3 action-icon ${this.state.isOperationShow ? '' : 'hide'}`}
            onClick={this.deleteShareItem}
            title={gettext('Delete')}
          >
          </span>
        </td>
      </tr>
    );
  }
}

class ShareList extends React.Component {

  render() {
    return (
      <div className="share-list-container">
        <table className="table-thead">
          <thead>
            <tr>
              <th width="25%">{gettext('Share to ')}</th>
              <th width="40%">{gettext('URL')}</th>
              <th width="20%">{gettext('Permission')}</th>
              <th width="15%"></th>
            </tr>
          </thead>
          <tbody>
            {this.props.items.map((item, index) => {
              return (
                <ShareItem
                  key={index}
                  item={item}
                  deleteShareItem={this.props.deleteShareItem}
                />
              );
            })}
          </tbody>
        </table>
      </div>
    );
  }
}

const propTypes = {
  // isGroupOwnedRepo: PropTypes.bool,
  itemPath: PropTypes.string.isRequired,
  // itemType: PropTypes.string.isRequired,
  repoID: PropTypes.string.isRequired,
};

class ShareWithOCM extends React.Component {

  constructor(props) {
    super(props);
    this.state = {
      selectedOption: null,
      errorMsg: [],
      permission: 'rw',
      ocmShares: [],
      toUser: '',
      toServerURL: '',
    };
    this.options = [];
    this.permissions = [];
    this.defaultOCMDesciption = '';
    this.defaultOCMShareType = 'user';
    this.defaultOCMResourceType = 'library';

  }

  handleSelectChange = (option) => {
    this.setState({selectedOption: option});
    this.options = [];
  }

  componentDidMount() {
    seafileAPI.listOCMShares().then((res) => {
      this.setState({ocmShares: res.data.ocm_share_list});
    }).catch(error => {
      let errMessage = Utils.getErrorMsg(error);
      toaster.danger(errMessage);
    });
  }

  startOCMShare = () => {
    // three steps:
    // 1. get ocm protocol info from remote server
    // 2. create ocm share on this server
    // 3. create ocm share received on remote server
    let { repoID, itemPath } = this.props;
    let { toServerURL, toUser, permission } = this.state;
    seafileAPI.getOCMProcotolRemoteServer(toServerURL).then((res) => {
      let ocm_protocol = res.data.supported_protocal;
      if (res.data.support_ocm) {
        seafileAPI.addOCMShare(toUser, toServerURL, repoID, itemPath, permission).then((res) => {
          let ocmShares = this.state.ocmShares;
          ocmShares.push(res.data);
          this.setState({ocmShares: ocmShares});
          let { shared_secret, repo_name, token, provider_id, owner, owner_name, permission } = res.data;
          let ocm_params = {
            toServerURL: toServerURL,
            shareWith: toUser,
            name: repo_name,        // protocol's field name is "name", actually is repoName
            description: this.defaultOCMDesciption,
            providerId: provider_id,
            owner: owner,
            sender: username,
            ownerDisplayName: owner_name,
            senderDisplayName: name, // sender nickname
            shareType: this.defaultOCMShareType,
            resourceType: this.defaultOCMResourceType,
            protocol: {
              name: ocm_protocol,
              options: {
                sharedSecret: shared_secret,
                permissions: permission,
                repoId: repoID,
                apiToken: token,
              }
            }
          };
          // add ocm share in this server, then send post to remote server
          seafileAPI.addOCMShareReceived(toServerURL, ocm_params).then((res) => {
            
          });
        });
      } else {
        toaster.danger('remote server does not support ocm');
      }
    }).catch(error => {
      let errMessage = Utils.getErrorMsg(error);
      toaster.danger(errMessage);
    });
  }

  handleToUserChange = (e) => {
    this.setState({
      toUser: e.target.value,
    });
  }

  handleURLChange = (e) => {
    this.setState({
      toServerURL: e.target.value,
    });
  }

  deleteShareItem = (sharedSecret, toServerURL) => {
    seafileAPI.deleteOCMShare(sharedSecret).then((res) => {
      let ocmShares = this.state.ocmShares.filter(item => {
        return item.shared_secret != sharedSecret;
      });
      this.setState({ocmShares: ocmShares});
      seafileAPI.deleteOCMShareReceived(sharedSecret, toServerURL).then((res) => {
        toaster.info('delete success.');
      })
    }).catch(error => {
      console.log(error);
      let errMessage = Utils.getErrorMsg(error);
      toaster.danger(errMessage);
    });
  }


  render() {
    let { ocmShares, toUser, toServerURL, permission } = this.state;
    return (
      <Fragment>
        <table>
          <thead>
            <tr>
              <th width="35%">{gettext('User')}</th>
              <th width="50%">{gettext('URL')}</th>
              {/* <th width="25%">{gettext('Permission')}</th> */}
              <th width="15%"></th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>
                <Input
                  value={toUser}
                  onChange={this.handleToUserChange}
                />
              </td>
              <td>
                <Input
                  value={toServerURL}
                  onChange={this.handleURLChange}
                />
              </td>
              {/* <td>
                <SharePermissionEditor
                  isTextMode={false}
                  isEditIconShow={false}
                  currentPermission={permission}
                  permissions={this.permissions}
                  onPermissionChanged={this.setPermission}
                />
              </td> */}
              <td>
                <Button onClick={this.startOCMShare}>{gettext('Submit')}</Button>
              </td>
            </tr>
          </tbody>
        </table>
        <ShareList
          items={ocmShares}
          deleteShareItem={this.deleteShareItem} 
        />
      </Fragment>
    );
  }
}

ShareWithOCM.propTypes = propTypes;

export default ShareWithOCM;
