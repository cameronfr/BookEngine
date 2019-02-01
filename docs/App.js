var API_URL = "https://asia-northeast1-traininggpu.cloudfunctions.net/GutenBert"

class App extends React.Component {

	style = {
		width: "700px",
		maxWidth: "700px",
		fontSize: "16px",
		fontFamily: "Arial",
		lineHeight: 1.3
	}

	constructor(props) {
		super(props)
		this.state = {
			textUnits: [],
			isWaitingForResults: false,
			searchText: "",
			errorMessage: "",
		}
	}

	fetchFromServer(sentence) {
		return fetch(API_URL, {
			method: "POST",
			mode: "cors",
			headers: {"Content-Type": "application/json"},
			body: JSON.stringify({sentence})
		}).then(res => res.json())
	}

	search() {
		this.fetchFromServer(this.state.searchText).then(res => {
			this.setState({textUnits: res.textUnits})
		}).catch(err => {
			this.setState({errorMessage: (err.response && err.response.data.msg) || "Error calling API"})
		})
	}

	render() {
		var updateSearchText = e => this.setState({searchText: e.target.value})
		var submitSearch = e => {e.preventDefault(); this.search()}

		return (
		 <div style={{display: "flex", justifyContent: "center"}}>
			 <div style={this.style}>
				 <SearchBar
					 onSubmit={submitSearch}
					 onChange={updateSearchText}
					 disabled={false}
					 placeholder={this.state.searchText}
					 value={this.state.searchText}
					/>
				 {this.state.textUnits.map(textUnit => <ResultItem textUnit={textUnit} />)}
			 </div>
		 </div>
		)
	}

}

class SearchBar extends React.Component{

	inputStyle = {
		width: "100%",
		boxShadow: "0px 1px 4px #ccc",
		border: "none",
		// height: "30px",
		borderRadius: "4px",
		padding: "10px",
		fontFamily: "inherit",
		fontSize: "inherit",
	}

  constructor(props){
    super(props);
  }

  render() {
    return (
      <div style={{width: "100%", boxSizing: "border-box"}}>
        <h5 className="">Enter a sentence</h5>
        <form onSubmit={this.props.onSubmit}>
	        <div uk-grid="true">
	          <input style={this.inputStyle}
							placeholder={this.props.placeholder}
							onChange={this.props.onChange}
							disabled={this.props.disabled}
							value={this.props.value}
						/>
	        </div>
        </form>
      </div>
    )
  }
}

class ResultItem extends React.Component {

	style = {
		// boxShadow: "0px 0px 3px #ccc",
		marginTop: "5px",
		marginBottom: "5px",
		padding: "10px",
		cursor: "pointer",
	}

	constructor(props) {
		super(props)
		this.state = {
			expanded: false,
			hovering: false,
		}
	}

	render() {
		var onHover = e => this.setState({hovering: true})
		var onUnHover = e => this.setState({hovering: false})
		var onClick = e => this.setState(state => ({expanded: !state.expanded}))
		var hoverStyle = this.state.hovering ? {boxShadow: "0px 0px 3px #ccc"} : {}
		var expandedStyle = this.state.expanded ? {height: "100px"} : {}

		return (
			<React.Fragment>
				<div style={{...this.style, ...hoverStyle, ...expandedStyle}}
					onMouseOver={onHover}
					onMouseLeave={onUnHover}
					onClick={onClick}>
					{this.props.textUnit}
				</div>
				<div style={{width: "100%", border: "none", height: "1px", backgroundColor: "black"}}/>
			</React.Fragment>
		)
	}
}

ReactDOM.render(<App />, document.getElementById('root'));
