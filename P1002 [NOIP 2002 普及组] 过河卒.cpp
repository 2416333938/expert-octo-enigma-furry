#include<bits/stdc++.h>
using namespace std;
int B[3],A[3],C[10][3],t;
long long dp[25][25];
bool Y(int a,int b){
	for(int i=1;i<=9;i++){
		if(a==C[i][1]&&b==C[i][2]){
			return 1;			
		}
	}
	return 0;
}
int main(){
	cin>>B[1]>>B[2]>>A[1]>>A[2];
	C[1][1]=A[1]+1;C[1][2]=A[2]-2;
	C[2][1]=A[1]+2;C[2][2]=A[2]-1;
	C[3][1]=A[1]+2;C[3][2]=A[2]+1;
	C[4][1]=A[1]+1;C[4][2]=A[2]+2;
	C[5][1]=A[1]-1;C[5][2]=A[2]+2;
	C[6][1]=A[1]-2;C[6][2]=A[2]+1;
	C[7][1]=A[1]-2;C[7][2]=A[2]-1;
	C[8][1]=A[1]-1;C[8][2]=A[2]-2;
	C[9][1]=A[1];C[9][2]=A[2];
	dp[0][0]=1; 
	for(int j=1;j<=B[2];j++){
	    if(Y(0,j)) dp[0][j]=0;
	    else dp[0][j]=dp[0][j-1];
	}
	
	for(int i=1;i<=B[1];i++){
	    if(Y(i,0)) dp[i][0]=0;
	    else dp[i][0]=dp[i-1][0];
	}

	for(int i=1;i<=B[1];i++){
	    for(int j=1;j<=B[2];j++){
	        if(Y(i,j)){
	            dp[i][j]=0;
	        }else{
	            dp[i][j]=dp[i-1][j]+dp[i][j-1];
	        }
	    }
	}
	
	cout<<dp[B[1]][B[2]];
}
