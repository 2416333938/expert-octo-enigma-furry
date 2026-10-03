#include <bits/stdc++.h>
using namespace std;
const long long mod = 1000000007;
int n, k;
char s[510];
long long F[510][510], G[510][510], star_[510][510], Q[510][510];

bool LP(int i){ return s[i]=='(' || s[i]=='?'; }
bool RP(int j){ return s[j]==')' || s[j]=='?'; }
bool ST(int i){ return s[i]=='*' || s[i]=='?'; }

int main(){
    scanf("%d %d", &n, &k);
    scanf("%s", s+1);

    // 预处理 star_[l][r]
    for(int l=1;l<=n;l++)
        for(int r=l;r<=n && r-l+1<=k;r++){
            if(ST(r)) star_[l][r]=1;
            else break;
        }

    for(int len=1; len<=n; len++){
        for(int l=1; l+len-1<=n; l++){
            int r = l+len-1;

            // ---- G[l][r] ----
            long long g = 0;
            if(LP(l) && RP(r)){
                if(len==2){
                    g = (g+1)%mod;                      // ()
                } else if(len>=3){
                    g = (g + star_[l+1][r-1]) % mod;    // (S)
                    g = (g + F[l+1][r-1]) % mod;        // (A)
                    for(int t=l+1; t<=r-2; t++){        // (SA)
                        if(!star_[l+1][t]) break;
                        g = (g + F[t+1][r-1]) % mod;
                    }
                    for(int t=r-2; t>=l+1; t--){        // (AS)
                        if(!star_[t+1][r-1]) break;
                        g = (g + F[l+1][t]) % mod;
                    }
                }
            }
            G[l][r] = g;

            // ---- F[l][r] ----
            long long f = g;
            for(int t=l; t<=r-1; t++)
                f = (f + Q[l][t] * F[t+1][r]) % mod;
            F[l][r] = f;

            // ---- 用 G[l][r] 更新 Q[l][t] ----
            Q[l][r] = (Q[l][r] + G[l][r]) % mod;        // 空串项
            for(int t=r+1; t<=n && t-r<=k; t++){
                if(!star_[r+1][t]) break;
                Q[l][t] = (Q[l][t] + G[l][r]) % mod;
            }
        }
    }

    printf("%lld\n", F[1][n]);
    return 0;
}
