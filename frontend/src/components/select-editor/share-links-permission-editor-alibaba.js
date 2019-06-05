import React from 'react';
import PropTypes from 'prop-types';
import { gettext } from '../../utils/constants';
import SelectEditor from './select-editor';

const propTypes = {
  permissionOptions: PropTypes.array.isRequired,
  currentPermission: PropTypes.string.isRequired,
  onPermissionChanged: PropTypes.func.isRequired
};

class ShareLinksPermissionEditorAlibaba extends React.Component {

  translatePermission = (permission) => {
    let isZHCN = window.app.config.lang === 'zh-cn';
    if (permission === 'previewOnCloud') {
      return isZHCN ? '仅云端只读': 'View-on-Cloud';
    }
    if (permission === 'editOnCloud') {
      return isZHCN ? '仅云端读写' : 'Edit-on-Cloud';
    }
  }

  render() {
    return (
      <SelectEditor 
        isTextMode={false}
        isEditIconShow={false}
        options={this.props.permissionOptions}
        currentOption={this.props.currentPermission}
        onOptionChanged={this.props.onPermissionChanged}
        translateOption={this.translatePermission}
      />
    );
  }
}

ShareLinksPermissionEditorAlibaba.propTypes = propTypes;

export default ShareLinksPermissionEditorAlibaba;
