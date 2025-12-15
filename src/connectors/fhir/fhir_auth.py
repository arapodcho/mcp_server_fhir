import requests
##get

class FHIRClient:
    def __init__(self, token_url, client_id, client_secret, grant_type, resource_value):        
        # 1. 설정 값 입력 
        self.token_url = token_url # FHIR_TOKEN_ENDPOINT
        self.client_id = client_id # FHIR_CLIENT_ID
        self.client_secret = client_secret # FHIR_CLIENT_SECRET
        self.grant_type = grant_type # FHIR_GRANT_TYPE (보통 Client_Credentials)
        self.resource_value = resource_value
        # 발급받은 토큰을 저장할 변수
        self.access_token = None

    def get_access_token(self):
        """
        인증 서버(Token Endpoint)에 자격 증명을 보내 Access Token을 받아옵니다.
        """
        if (self.token_url is not None) and (self.client_id is not None) and (self.client_secret is not None) and (self.grant_type == "Client_Credentials"):
            
            payload = {
                "grant_type": self.grant_type,
                "client_id": self.client_id,
                "client_secret": self.client_secret,            
                # 만약 scope가 필요하다면 아래 주석 해제 (예: "system/*.read")
                # "scope": "system/*.read" 
            }
            if self.resource_value:
                payload["resource"] = self.resource_value

            try:
                # POST 요청으로 토큰 발급 시도
                response = requests.post(self.token_url, data=payload)
                response.raise_for_status() # 200 OK가 아니면 에러 발생
                
                token_data = response.json()
                self.access_token = token_data.get("access_token")
                
                print(f"[Success] 토큰 발급 완료: {self.access_token[:10]}...")
                return self.access_token

            except requests.exceptions.RequestException as e:
                print(f"[Error] 토큰 발급 실패: {e}")
                if response is not None:
                    print(f"서버 응답: {response.text}")
                return None
        else:
            self.access_token = None
            return self.access_token        

    def get_headers(self):
        """
        FHIR 요청 시 사용할 헤더를 생성합니다 (Authorization 포함).
        """
        if not self.access_token:
            self.get_access_token() # 토큰이 없으면 발급 시도

        result_value ={
                "Accept": "application/fhir+json",                                
            }
        
        if self.access_token:
            result_value["Authorization"] = f"Bearer {self.access_token}"
        
        return result_value