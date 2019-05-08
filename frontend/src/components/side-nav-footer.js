import React from 'react';
import { gettext, mediaUrl, siteRoot } from '../utils/constants';

class SideNavFooter extends React.Component {

  constructor(props) {
    super(props);
    this.state = {
      isAboutDialogShow: false,
    };
  }

  onAboutDialogToggle = () => {
    this.setState({isAboutDialogShow: !this.state.isAboutDialogShow});
  }

  render() {
    if (window.app.config.lang === 'zh-cn') {
      return (
        <div className="side-nav-footer">
          <div rel="noopener noreferrer" className="item">
            <img src={mediaUrl + 'img/alibaba-information-platfrom.png'}  height="22" style={{marginRight: 'auto',}} />
          </div>
          <a href={siteRoot + 'help/'} target="_blank" rel="noopener noreferrer" className="item last-item" style={{marginLeft: 'auto',}}>{'帮助'}</a>
        </div>
      );
    } else {
      return (
        <div className="side-nav-footer">
          <div rel="noopener noreferrer" className="item">
            <img src={mediaUrl + 'img/alibaba-information-platfrom.png'}  height="22" style={{marginRight: 'auto',}} />
          </div>
          <a href={siteRoot + 'help/'} target="_blank" rel="noopener noreferrer" className="item last-item" style={{marginLeft: 'auto',}}>{'Help'}</a>
        </div>
      );
    }
  }
}

export default SideNavFooter;
