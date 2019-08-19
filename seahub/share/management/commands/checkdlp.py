# coding=utf-8
# !/usr/bin/env python

import pymssql
import ConfigParser


class MSSQL:
    def __init__(self):
        cf = ConfigParser.ConfigParser()
        cf.read("/wls/seafile/check-dlp/mssql.conf")
        self.host = cf.get("DB", "host")
        self.user = cf.get("DB", "user")
        self.pwd = cf.get("DB", "pwd")
        self.db = cf.get("DB", "db")

    def __GetConnect(self):
        """
        get connetion info
        response: conn.cursor()
        """
        # if not self.db:
        #    raise(NameError,"no db conf file found")

        self.conn = pymssql.connect(host=self.host, user=self.user, password=self.pwd, database=self.db, timeout=5,
                                    login_timeout=2, charset="utf8")
        cur = self.conn.cursor()
        if not cur:
            raise (NameError, "fail connecting to DB")
        else:
            return cur

    ##verify DB connection
    def VerifyConnection(self):
        try:
            if self.host == '':
                return False
            conn = pymssql.connect(host=self.host, user=self.user, password=self.pwd, database=self.db, timeout=1,
                                   login_timeout=1, charset="utf8")
            return True
        except:
            return False

    def ExecQuery(self, sql):
        """
        execute query
        get a list including tuple, elements of list are row of record, elements of tuple is fields

        demo
                ms = MSSQL(host="localhost",user="sa",pwd="123456",db="PythonWeiboStatistics")
                resList = ms.ExecQuery("SELECT id,NickName FROM WeiBoUser")
                for (id,NickName) in resList:
                    print str(id),NickName
        """
        cur = self.__GetConnect()
        cur.execute(sql)
        resList = cur.fetchall()
        # resList = cur.description
        # close connection after querying
        self.conn.close()
        return resList

    def ExecNonQuery(self, sql):
        """
        execute no query
        demo
            cur = self.__GetConnect()
            cur.execute(sql)
            self.conn.commit()
            self.conn.close()
        """
        cur = self.__GetConnect()
        cur.execute(sql)
        self.conn.commit()
        self.conn.close()

    def ExecStoreProduce(self, sql):
        """
        execute query
        get a list including tuple, elements of list are row of record, elements of tuple is fields

        demo:
                ms = MSSQL(host="localhost",user="sa",pwd="123456",db="PythonWeiboStatistics")
                resList = ms.ExecQuery("SELECT id,NickName FROM WeiBoUser")
                for (id,NickName) in resList:
                    print str(id),NickName
        """
        cur = self.__GetConnect()
        cur.execute(sql)
        resList = cur.fetchall()
        self.conn.commit()
        # close connection after querying
        self.conn.close()
        return resList

    def CheckDLP(self, file_path, filesize, mtime):
        """
        according filepath check DLP scan result
        """
        result = 0
        #if 'huangminglong' in file_path:return 2;
        filepath = file_path.replace('/', '\\')
        # filepath=filepath1.replace('\'','\'\'')
        # input use /,replaced by \ for windows sql server
        print 'windows path: ' + filepath
        filepath = self.sqlExcape(filepath)
        cur = self.__GetConnect()
        filepath1 = filepath.replace('\'', '\'\'')

        sql1 = "select count(*) as cnt from [wbsn-data-security]..[PA_DSCVR_FILES] where FILEPATH like N'%" + filepath1 + "' and FILE_SIZE=%d and [POLICY_CATEGORIES]= 'permit'" % filesize
        # _ is the shift char in sql server, put N behind of like
        # print sql1.encode('utf-8')
        cur.execute(sql1.encode('utf-8'))
        resList1 = cur.fetchall()
        if int(resList1[0][0]) > 0:
            result = 1

            # sql2 = "select count(*) as cnt from [wbsn-data-security]..[PA_DSCVR_FILES] where FILEPATH like N'%" + filepath + "' and FILE_SIZE=%d and [POLICY_CATEGORIES] = 'block_sec; permit'" % filesize
        sql2 = "select count(*) as cnt from [wbsn-data-security]..[PA_DSCVR_FILES] where FILEPATH like N'%" + filepath1 + "' and charindex('block',[POLICY_CATEGORIES])>0 and FILE_SIZE=%d" % filesize
        print sql2.encode('utf-8')
        cur.execute(sql2.encode('utf-8'))
        resList2 = cur.fetchall()
        if int(resList2[0][0]) > 0:
            result = 2

        self.conn.commit()
        self.conn.close()
        # print filepath
        # print filesize
        print str(result) + ' (0 no scan,  1 scan ok, 2 scan not ok)'
        ## result=1
        ## just for test when DLP is not working
        return result

    # Created by WANGZEXIN289
    # 功能：对DLP的查询SQL中包含的特殊字符进行转义
    def sqlExcape(self, partial_path):
        specialChar = set(['[', '%', '_', '^'])
        for char in specialChar:
            partial_path = partial_path.replace(char, '[%s]' % char)
        return partial_path


def main():
    ms = MSSQL()
    fp = 'pengjq@pingan.com.cn\\9e516f8c-741a-49c1-b8ae-00aaea2ec237_demo\\6.jpg'
    # \ is the shift char in python
    print unicode(fp, 'utf-8')
    result = ms.CheckDLP(fp, 59792, 2015 - 6 - 11)
    print result
    # sqlquery="select * from [wbsn-data-security]..pa_dscvr_inc_breach_cnts"
    # sqlconn=MSSQL()
    # res=sqlconn.ExecQuery(sqlquery)
    # for data in res:
    #        print data
    #       print '%s%s%s' % tuple([str(s).title().ljust(COLSIZ) for s in data])


if __name__ == '__main__':
    main()
