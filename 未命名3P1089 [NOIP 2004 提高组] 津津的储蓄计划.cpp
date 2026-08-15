#include<bits/stdc++.h>
using namespace std;
int y,yd,x,xyyd;
int main(){
	cin>>y>>yd;
	while(y>0){
		y-=1;
		x+=1;
		xyyd+=1;
		if(x>=yd){
			x-=yd;y+=1;
		}
	}
	cout<<xyyd;
}
