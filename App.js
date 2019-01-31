var API_URL = "https://asia-northeast1-traininggpu.cloudfunctions.net/GutenBert"

class App extends React.Component {

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
		 <div>
			 <SearchBar
				 onSubmit={submitSearch}
				 onChange={updateSearchText}
				 disabled={false}
				 placeholder={this.state.searchText}
				 value={this.state.searchText}
				/>
			 {this.state.textUnits.map(textUnit => <ResultItem textUnit={textUnit} />)}
		 </div>
		)
	}

}

class SearchBar extends React.Component{
  constructor(props){
    super(props);
  }

  render() {
    return (
      <div className="uk-card">
        <h5 className="uk-text-left uk-text-bold">Enter a sentence</h5>
        <form onSubmit={this.props.onSubmit}>
	        <div uk-grid="true">
	          <input className={"uk-overflow-auto uk-box-shadow-small uk-input" + (this.props.success ? " uk-form-success" : "") + (this.props.danger ? " uk-form-danger" : "")}
	          placeholder={this.props.placeholder} onChange={this.props.onChange} disabled={this.props.disabled} value={this.props.value} />
	        </div>
        </form>
      </div>
    )
  }
}

class ResultItem extends React.Component {

	style = {
		boxShadow: "0px 1px 4px #ccc",
		margin: "10px",
		padding: "10px",
	}

	constructor(props) {
		super(props)
		this.state = {
			expanded: false,

		}
	}

	render() {
		return <div style={this.style}>
			{this.props.textUnit}
		</div>
	}
}

ReactDOM.render(<App />, document.getElementById('root'));
