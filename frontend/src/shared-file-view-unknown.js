import React from 'react';
import ReactDOM from 'react-dom';
import SharedFileViewPingan from './components/shared-file-view/shared-file-view-pingan';
import SharedFileViewTip from './components/shared-file-view/shared-file-view-tip';

const { err } = window.shared.pageOptions;

class SharedFileViewImage extends React.Component {
  render() {
    return <SharedFileViewPingan content={<FileContent />} />;
  }
}

class FileContent extends React.Component {
  render() {
    if (err) {
      return <SharedFileViewTip />;
    }
  }
}

ReactDOM.render(
  <SharedFileViewImage />,
  document.getElementById('wrapper')
);
