import React from 'react';
import { gettext } from '../../utils/constants';

const { 
  nameLabel,
  enableUpdateUserInfo,
  enableUserSetContactEmail
} = window.app.pageOptions;

class UserBasicInfoForm extends React.Component {

  constructor(props) {
    super(props);
    const {
      emp_name,
      nick_name,
      post_name,
      post_name_en,
      dept_name,
      dept_name_en,
      contact_email,
      login_id,
      name
    } = this.props.userInfo;
    this.state = {
      emp_name: emp_name,
      nick_name: nick_name,
      post_name: post_name,
      post_name_en: post_name_en,
      dept_name: dept_name,
      dept_name_en: dept_name_en,
      contactEmail: contact_email,
      loginID: login_id,
      name: name
    };
  }

  handleNameInputChange = (e) => {
    this.setState({
      name: e.target.value
    });
  }

  handleContactEmailInputChange = (e) => {
    this.setState({
      contactEmail: e.target.value
    });
  }

  handleSubmit = (e) => {
    e.preventDefault();
    let data = {
      name: this.state.name
    };
    if (enableUserSetContactEmail) {
      data.contact_email = this.state.contactEmail;
    }
    this.props.updateUserInfo(data);
  }

  render() {
    const {
      emp_name,
      nick_name,
      post_name,
      post_name_en,
      dept_name,
      dept_name_en,
      contactEmail,
      loginID,
      name
    } = this.state;
    let isZHCN = window.app.config.lang === 'zh-cn';

    return (
      <form action="" method="post" onSubmit={this.handleSubmit}>

        <div className="form-group row">
          <label className="col-sm-1 col-form-label" htmlFor="name">{isZHCN ? '姓名：' : 'Name:' }</label>
          <div className="col-sm-5">
            <input className="form-control" id="name" type="text" name="name" value={emp_name} disabled />
          </div>
        </div>

        <div className="form-group row">
          <label className="col-sm-1 col-form-label" htmlFor="nickname">{isZHCN ? '花名：' : 'Nickname:'}</label>
          <div className="col-sm-5">
            <input className="form-control" id="nickname" type="text" name="nickname" value={nick_name} disabled />
          </div>
        </div>

        <div className="form-group row">
          <label className="col-sm-1 col-form-label" htmlFor="position">{isZHCN ? '职位：' : 'Position:'}</label>
          <div className="col-sm-5">
            <input className="form-control" id="position" type="text" name="position" value={isZHCN ? post_name : post_name_en} disabled />
          </div>
        </div>

        <div className="form-group row">
          <label className="col-sm-1 col-form-label" htmlFor="department">{isZHCN ? '部门：' : 'Deparment'}</label>
          <div className="col-sm-5">
            <input className="form-control" id="department" type="text" name="department" value={isZHCN ? dept_name : dept_name_en} disabled />
          </div>
        </div>
      </form>
    );
  }
}

export default UserBasicInfoForm;
