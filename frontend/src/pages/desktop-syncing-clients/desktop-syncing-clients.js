import React, { Component } from 'react';

class Content extends Component {
  constructor(props) {
    super(props);

  }

  handleClientClick = (e) => {
    e.preventDefault();
    window.location.href = e.currentTarget.getElementsByTagName('a')[0].href;
  }

  render() {
    let isZHCN = window.app.config.lang === 'zh-cn';
    return (
      <div className="d-flex justify-content-around mt-8">
        <div className="d-flex cursor-pointer" onClick={this.handleClientClick.bind(this)}>
          <div className="mr-4"><img src="/media/img/windows.png" alt="" className="pic" />
          </div>
          <div>
            <h3>{isZHCN ? 'Windows 客户端' : 'Client for Windows'}</h3>
            <p>{isZHCN ? '可运行于 Windows 7/8/10' : 'Runs on 7/8/10'}</p>
            <a href={isZHCN ? window.app.pageOptions.windowsClientPublicDownloadUrl : window.app.pageOptions.windowsClientPublicDownloadUrlEn} className="download-op">{isZHCN ? '下载 '+window.app.pageOptions.windowsClientVersion : 'Download '+window.app.pageOptions.windowsClientVersionEn}</a>
          </div>
        </div>
        <div className="d-flex cursor-pointer" onClick={this.handleClientClick.bind(this)}>
          <div className="mr-4"><img src="/media/img/apple.png" alt="" className="pic" />
          </div>
          <div>
            <h3>{isZHCN ? 'Mac 客户端' : 'Client for Mac'}</h3>
            <p>{isZHCN ? '支持 Mac OS X 10.7+' : 'Runs on Mac OS X 10.7 or above'}</p>
            <a href={isZHCN ? window.app.pageOptions.appleClientPublicDownloadUrl : window.app.pageOptions.appleClientPublicDownloadUrlEn} className="download-op">{isZHCN ? '下载 '+window.app.pageOptions.appleClientVersion : 'Download '+window.app.pageOptions.appleClientVersionEn}</a>
          </div>
        </div>
      </div>
    )
  }
}


class DesktopSyncingClients extends Component {

  render() {
    let isZHCN = window.app.config.lang === 'zh-cn';
    return (
      <div className="main-panel-center">
        <div className="cur-view-container">
          <div className="cur-view-path">
            <h3 className="sf-heading">{isZHCN ? '桌面同步客户端' : 'Desktop Syncing Clients'}</h3>
          </div>
          <div className="cur-view-content">
            <Content data={this.state} />
          </div>
        </div>
      </div>
    );
  }
}

export default DesktopSyncingClients;
