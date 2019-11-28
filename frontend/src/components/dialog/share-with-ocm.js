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

// class UserItem extends React.Component {

//   constructor(props) {
//     super(props);
//     this.state = {
//       isOperationShow: false
//     };
//   }
  
//   onMouseEnter = () => {
//     this.setState({isOperationShow: true});
//   }

//   onMouseLeave = () => {
//     this.setState({isOperationShow: false});
//   }

//   deleteShareItem = () => {
//     let item = this.props.item;
//     this.props.deleteShareItem(item.user_info.name);
//   }
  
//   onChangeUserPermission = (permission) => {
//     let item = this.props.item;
//     this.props.onChangeUserPermission(item, permission);
//   }

//   render() {
//     let item = this.props.item;
//     let currentPermission = item.is_admin ? 'admin' : item.permission;
//     return (
//       <tr onMouseEnter={this.onMouseEnter} onMouseLeave={this.onMouseLeave}>
//         <td className="name">{item.user_info.nickname}</td>
//         <td>
//           <SharePermissionEditor 
//             isTextMode={true}
//             isEditIconShow={this.state.isOperationShow}
//             currentPermission={currentPermission}
//             permissions={this.props.permissions}
//             onPermissionChanged={this.onChangeUserPermission}
//           />
//         </td>
//         <td>
//           <span
//             className={`sf2-icon-x3 action-icon ${this.state.isOperationShow ? '' : 'hide'}`}
//             onClick={this.deleteShareItem} 
//             title={gettext('Delete')}
//           >
//           </span>
//         </td>
//       </tr>
//     );
//   }
// }

// class UserList extends React.Component {

//   render() {
//     let items = this.props.items;
//     return (
//       <tbody>
//         {items.map((item, index) => {
//           return (
//             <UserItem 
//               key={index} 
//               item={item} 
//               permissions={this.props.permissions}
//               deleteShareItem={this.props.deleteShareItem}
//               onChangeUserPermission={this.props.onChangeUserPermission}
//             />
//           );
//         })}
//       </tbody>
//     );
//   }
// }

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
    this.ocmShareType = 'user';
    this.ocmShareresourceType = 'library';

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
      console.log('=== from toServerURL res = ')
      console.log(res)
      let ocm_protocol = res.data.supported_protocal;
      if (res.data.support_ocm) {
        seafileAPI.AddOCMShare(toUser, toServerURL, repoID, itemPath, permission).then((res) => {
          let { shared_secret, repo_name, token, provider_id, owner, owner_name, permission } = res.data;
          let ocm_params = {
            toServerURL: toServerURL,
            shareWith: toUser,
            repoName: repo_name,
            description: 'desciption',
            providerId: provider_id,
            owner: owner,
            sender: username,
            ownerDisplayName: owner_name,
            senderDisplayName: name, // sender nickname
            shareType: this.ocmShareType,
            resourceType: this.ocmShareType,
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
          seafileAPI.AddOCMShareReceived(toServerURL, ocm_params).then((res) => {
            
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

  setPermission = (permission) => {
    this.setState({permission: permission});
  }


  render() {
    let { ocmShares, toUser, toServerURL, permission } = this.state;
    return (
      <Fragment>
        <table>
          <thead>
            <tr>
              <th width="25%">{gettext('User')}</th>
              <th width="35%">{gettext('URL')}</th>
              <th width="25%">{gettext('Permission')}</th>
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
              <td>
                <SharePermissionEditor
                  isTextMode={false}
                  isEditIconShow={false}
                  currentPermission={permission}
                  permissions={this.permissions}
                  onPermissionChanged={this.setPermission}
                />
              </td>
              <td>
                <Button onClick={this.startOCMShare}>{gettext('Submit')}</Button>
              </td>
            </tr>
          </tbody>
        </table>
        <div className="share-list-container">
          list
          <table className="table-thead-hidden">
            <thead>
              <tr>
                <th width="50%">{gettext('User')}</th>
                <th width="35%">{gettext('Permission')}</th>
                <th width="15%"></th>
              </tr>
            </thead>
            {/* <UserList 
              items={sharedItems}
              permissions={this.permissions}
              deleteShareItem={this.deleteShareItem} 
              onChangeUserPermission={this.onChangeUserPermission}
            /> */}
          </table>
        </div>
      </Fragment>
    );
  }
}

ShareWithOCM.propTypes = propTypes;

export default ShareWithOCM;
