import React, { Component, Fragment } from 'react';
import moment from 'moment';
import { Modal, ModalHeader, ModalBody, ModalFooter, Button } from 'reactstrap';
import { seafileAPI } from '../../utils/seafile-api';
import { Utils } from '../../utils/utils';
import classnames from 'classnames';
import { gettext, serviceURL } from '../../utils/constants';


class ContentVerifying extends Component {

  constructor(props) {
    super(props);
    this.state = {
      modalOpen: false,
      modalContent: ''
    };
  }

  toggleModal = () => {
    this.setState({
      modalOpen: !this.state.modalOpen
    });
  }

  showModal = (options) => {
    this.toggleModal();
    this.setState({modalContent: options.content});
  }

  render() {
    const { loading, errorMsg, items } = this.props;
    if (loading) {
      return <span className="loading-icon loading-tip"></span>;
    } else if (errorMsg) {
      return <p className="error text-center">{errorMsg}</p>;
    } else {
      const emptyTip = (
        <div className="empty-tip">
          <h2>{'你还没有需要审核的文件外链'}</h2>
        </div>
      );

      const table = (
        <React.Fragment>
          <table className="table-hover">
            <thead>
              <tr>
                <th width="4%">{/*icon*/}</th>
                <th width="31%">{gettext('Name')}</th>
                <th width="20%">{'来源'}</th>
                <th width="15%">{'状态'}</th>
                <th width="20%">{'生成时间'}</th>
                <th width="10%">{/*Operations*/}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, index) => {
                return (<ItemVerifying key={index} item={item} showModal={this.showModal} onRemoveLink={this.props.onRemoveLink}/>);
              })}
            </tbody>
          </table>
          <Modal isOpen={this.state.modalOpen} toggle={this.toggleModal} centered={true}>
            <ModalHeader toggle={this.toggleModal}>{'审核状态'}</ModalHeader>
            <ModalBody>
              {this.state.modalContent}
            </ModalBody>
            <ModalFooter>
              <Button color="secondary" onClick={this.toggleModal}>{'关闭'}</Button>
            </ModalFooter>
          </Modal>
        </React.Fragment>
      );

      return items.length ? table : emptyTip;
    }
  }
}

class ItemVerifying extends Component {

  constructor(props) {
    super(props);
    this.state = {
      showOpIcon: false,
    };
    this.permissionOptions = ['Preview only', 'Preview and download'];
  }

  handleMouseOver = () => {
    this.setState({showOpIcon: true});
  }

  handleMouseOut = () => {
    this.setState({showOpIcon: false});
  }

  viewStatus = (e) => {
    e.preventDefault();
    let strArray = this.props.item.verbose_status_str.split(';');
    let ele = strArray.map((str, i) => {
      return (
        <li key={i}>{str}</li>
      );
    })
    this.props.showModal({content: ele});
  }

  removeLink = (e) => {
    e.preventDefault();
    this.props.onRemoveLink(this.props.item);
  }

  getLinkParams = () => {
    let item = this.props.item;
    let fileName = item.path.substr(item.path.lastIndexOf('/') + 1);
    let iconUrl = Utils.getFileIconUrl(fileName);
    let linkUrl = item.link;
    let profileUrl = `${serviceURL}/profile/${item.username}`;

    return { iconUrl, linkUrl, profileUrl, fileName };
  }

  render() {
    const item = this.props.item;
    let { iconUrl, linkUrl, profileUrl, fileName } = this.getLinkParams();
    let iconVisibility = this.state.showOpIcon ? '' : ' invisible';
    let deleteIconClassName = 'sf2-icon-delete action-icon' + iconVisibility;
    let statusStr = '';
    if (item.short_status_str === 'Verifing') {
      statusStr = '正在审核';
    } else if (item.short_status_str === 'Approved') {
      statusStr = '审核通过';
    } else if (item.short_status_str === 'Rejected') {
      statusStr = '否决';
    }
    return (
      <tr onMouseEnter={this.handleMouseOver} onMouseLeave={this.handleMouseOut}>
        <td><img src={iconUrl} width="24" /></td>
        <td><a href={linkUrl} target="_blank">{fileName}</a></td>
        <td><a href={profileUrl} target="_blank">{item.username}</a></td>
        <td><a href="#"  onClick={this.viewStatus}>{statusStr}</a></td>
        <td title={moment(item.ctime).format('llll')}>{moment(item.ctime).fromNow()}</td>
        <td>
          <a href="#" className={deleteIconClassName} title={gettext('Remove')} onClick={this.removeLink}></a>
        </td>
      </tr>
    );
  }
}

class ContentVerified extends Component {

  constructor(props) {
    super(props);
    this.state = {
      modalOpen: false,
      modalContent: ''
    };
  }

  toggleModal = () => {
    this.setState({
      modalOpen: !this.state.modalOpen
    });
  }

  showModal = (options) => {
    this.toggleModal();
    this.setState({modalContent: options.content});
  }

  render() {
    const { loading, errorMsg, items } = this.props;
    if (loading) {
      return <span className="loading-icon loading-tip"></span>;
    } else if (errorMsg) {
      return <p className="error text-center">{errorMsg}</p>;
    } else {
      const emptyTip = (
        <div className="empty-tip">
          <h2>{'你还没有审核完成的文件外链'}</h2>
        </div>
      );

      const table = (
        <React.Fragment>
          <table className="table-hover">
            <thead>
              <tr>
                <th width="4%">{/*icon*/}</th>
                <th width="30%">{gettext('Name')}</th>
                <th width="23%">{'来源'}</th>
                <th width="10%">{'状态'}</th>
                <th width="12%">{'生成时间'}</th>
                <th width="12%">{'过期时间'}</th>
                <th width="12%">{'首次下载时间'}</th>
                <th width="8%">{'访问次数'}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, index) => {
                return (<ItemVerified key={index} item={item} showModal={this.showModal} onRemoveLink={this.props.onRemoveLink}/>);
              })}
            </tbody>
          </table>
          <Modal isOpen={this.state.modalOpen} toggle={this.toggleModal} centered={true}>
            <ModalHeader toggle={this.toggleModal}>{'审核状态'}</ModalHeader>
            <ModalBody>
              {this.state.modalContent}
            </ModalBody>
            <ModalFooter>
              <Button color="secondary" onClick={this.toggleModal}>{'关闭'}</Button>
            </ModalFooter>
          </Modal>
        </React.Fragment>
      );

      return items.length ? table : emptyTip;
    }
  }
}

class ItemVerified extends Component {

  constructor(props) {
    super(props);
    this.state = {
      showOpIcon: false,
    };
    this.permissionOptions = ['Preview only', 'Preview and download'];
  }

  handleMouseOver = () => {
    this.setState({showOpIcon: true});
  }

  handleMouseOut = () => {
    this.setState({showOpIcon: false});
  }

  viewStatus = (e) => {
    e.preventDefault();
    let strArray = this.props.item.verbose_status_str.split(';');
    let ele = strArray.map((str, i) => {
      return (
        <li key={i}>{str}</li>
      );
    })
    this.props.showModal({content: ele});
  }

  removeLink = (e) => {
    e.preventDefault();
    this.props.onRemoveLink(this.props.item);
  }

  renderExpriedData = () => {
    let item = this.props.item;
    if (!item.expire_date) {
      return (
        <Fragment>--</Fragment>
      );
    }
    let expire_date = moment(item.expire_date).format('YYYY-MM-DD');
    return (
      <Fragment>
        {item.is_expired ?
          <span className="error">{expire_date}</span> :
          expire_date
        }
      </Fragment>
    );
  }

  getLinkParams = () => {
    let item = this.props.item;
    let fileName = item.path.substr(item.path.lastIndexOf('/') + 1);
    let iconUrl = Utils.getFileIconUrl(fileName);
    let linkUrl = item.link;
    let profileUrl = `${serviceURL}/profile/${item.username}`;

    return { iconUrl, linkUrl, profileUrl, fileName };
  }

  render() {
    const item = this.props.item;
    let { iconUrl, linkUrl, profileUrl, fileName } = this.getLinkParams();
    let iconVisibility = this.state.showOpIcon ? '' : ' invisible';
    let deleteIconClassName = 'sf2-icon-delete action-icon' + iconVisibility;
    let statusStr = '';
    if (item.short_status_str === 'Verifing') {
      statusStr = '正在审核';
    } else if (item.short_status_str === 'Approved') {
      statusStr = '审核通过';
    } else if (item.short_status_str === 'Rejected') {
      statusStr = '否决';
    }
    return (
      <tr onMouseEnter={this.handleMouseOver} onMouseLeave={this.handleMouseOut}>
        <td><img src={iconUrl} width="24" /></td>
        <td><a href={linkUrl} target="_blank">{fileName}</a></td>
        <td><a href={profileUrl} target="_blank">{item.username}</a></td>
        <td><a href="#"  onClick={this.viewStatus}>{statusStr}</a></td>
        <td title={moment(item.ctime).format('llll')}>{moment(item.ctime).fromNow()}</td>
        <td>{this.renderExpriedData()}</td>
        <td>{item.first_download_time}</td>
        <td>{item.view_cnt}</td>
      </tr>
    );
  }
}


class VerifyingLinks extends Component {

  constructor(props) {
    super(props);
    this.state = {
      loading: true,
      errorMsg: '',
      items: [],
      isShowVerifying: true,
    };
  }

  componentDidMount() {
    this.getVerifyShareLinks(this.state.isShowVerifying).then((res) => {
      let linkdata = res.data.data.map(item => {
        //return new VerifyLinkInfo(item);
        return item;
      });
      this.setState({
        loading: false,
        items: linkdata,
      });
    });

  }

  getVerifyShareLinks(isShowVerifying) {
    let status = isShowVerifying ? 0 : 1;
    const url = seafileAPI.server + '/api/v2.1/verify-share-links/?status=' + status;
    return seafileAPI.req.get(url);
  }

  deleteVerifyShareLinks(token) {
    const url = seafileAPI.server + '/api/v2.1/verify-share-links/' + token + '/';
    return seafileAPI.req.delete(url);
  }

  onRemoveLink = (item) => {
    this.deleteVerifyShareLinks(item.token).then(() => {
      let items = this.state.items.filter(Item => {
        return Item.token !== item.token;
      });
      this.setState({items: items});
      // TODO: show feedback msg
      // gettext("Successfully deleted 1 item")
    }).catch((error) => {
    // TODO: show feedback msg
    });
  }

  showVerifyContent = (isShowVerifyingContent) => {
    this.getVerifyShareLinks(isShowVerifyingContent).then((res) => {
      let linkdata = res.data.data.map(item => {
        //return new VerifyLinkInfo(item);
        return item;
      });
      this.setState({
        loading: false,
        items: linkdata,
      });
    });
    this.setState({
      isShowVerifying: isShowVerifyingContent,
    });
  }

  render() {
    let { isShowVerifying } = this.state;
    return (
      <div className="main-panel-center">
        <div className="cur-view-container">
          <div className="cur-view-path share-upload-nav">
            <ul className="nav">
              <li className="nav-item">
                <a onClick={() => {this.showVerifyContent(true);}} className={classnames('nav-link', { active: isShowVerifying })}>{'正在审核的链接'}</a>
              </li>
              <li className="nav-item">
                <a onClick={() => {this.showVerifyContent(false);}} className={classnames('nav-link', { active: !isShowVerifying })}>{'已审核的链接'}</a>
              </li>
            </ul>
          </div>
          <div className="cur-view-content">
            {isShowVerifying ?
              <ContentVerifying
                loading={this.state.loading}
                errorMsg={this.state.errorMsg}
                items={this.state.items}
                sortBy={this.state.sortBy}
                sortOrder={this.state.sortOrder}
                sortItems={this.sortItems}
                onRemoveLink={this.onRemoveLink}
              />
              :
              <ContentVerified
                loading={this.state.loading}
                errorMsg={this.state.errorMsg}
                items={this.state.items}
                sortBy={this.state.sortBy}
                sortOrder={this.state.sortOrder}
                sortItems={this.sortItems}
                onRemoveLink={this.onRemoveLink}
              />
            }
          </div>
        </div>
      </div>
    );
  }
}

export default VerifyingLinks;