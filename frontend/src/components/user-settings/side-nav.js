import React from 'react';
import { gettext } from '../../utils/constants';

class SideNav extends React.Component {

  constructor(props) {
    super(props);
  }

  render() {
    return (
      <ul className="list-group list-group-flush">
        <li className="list-group-item"><a href="#user-basic-info">{gettext('Profile')}</a></li>
        <li className="list-group-item"><a href="#lang-setting">{gettext('Language')}</a></li>
      </ul>
    );
  }
}

export default SideNav; 
