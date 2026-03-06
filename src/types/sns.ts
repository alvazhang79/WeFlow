export interface SnsLivePhoto {
    url: string
    thumb: string
    token?: string
    key?: string
    encIdx?: string
}

export interface SnsMedia {
    url: string
    thumb: string
    md5?: string
    token?: string
    key?: string
    encIdx?: string
    livePhoto?: SnsLivePhoto
}

export interface SnsCommentEmoji {
    url: string
    md5: string
    width: number
    height: number
    encryptUrl?: string
    aesKey?: string
}

export interface SnsComment {
    id: string
    nickname: string
    username?: string
    content: string
    refCommentId: string
    refNickname?: string
    refUsername?: string
    emojis?: SnsCommentEmoji[]
}

export interface SnsLikeDetail {
    nickname: string
    username?: string
    wxid?: string
    alias?: string
    wechatId?: string
    remark?: string
    nickName?: string
    displayName: string
    avatarUrl?: string
    source: 'xml' | 'legacy'
}

export interface SnsCommentDetail {
    id: string
    nickname: string
    username?: string
    wxid?: string
    alias?: string
    wechatId?: string
    remark?: string
    nickName?: string
    displayName: string
    avatarUrl?: string
    content: string
    refCommentId: string
    refNickname?: string
    refUsername?: string
    refWxid?: string
    refAlias?: string
    refWechatId?: string
    refRemark?: string
    refNickName?: string
    refDisplayName?: string
    refAvatarUrl?: string
    emojis?: SnsCommentEmoji[]
    source: 'xml' | 'legacy'
}

export interface SnsPost {
    id: string
    tid?: string       // 数据库主键（雪花 ID），用于精确删除
    username: string
    nickname: string
    avatarUrl?: string
    createTime: number
    contentDesc: string
    type?: number
    media: SnsMedia[]
    likes: string[]
    comments: SnsComment[]
    likesDetail?: SnsLikeDetail[]
    commentsDetail?: SnsCommentDetail[]
    rawXml?: string
    linkTitle?: string
    linkUrl?: string
    isProtected?: boolean  // 是否受保护（已安装时标记）
}

export interface SnsLinkCardData {
    title: string
    url: string
    thumb?: string
}
