var API_URL = "https://asia-northeast1-traininggpu.cloudfunctions.net/ForumBert"

var fetchFromServer = (url, body) => {
	return fetch(url, {
		method: "POST",
		mode: "cors",
		headers: {"Content-Type": "application/json"},
		body: JSON.stringify(body)
	}).then(res => res.json())
}

var exampleQueries = [
	"Israel attacks palestinian refugees",
	"Hamas attacks Israel",
	"Global deforestation",
	"Looking for inspiration for his next project",
	"seasonal harvest doing well",
	"10 things you might not know ",
	"Forest fires cause",
	"Other liveable planets"
]

class App extends React.Component {

	style = {
		width: "700px",
		paddingLeft: "10px",
		paddingRight: "10px",
		maxWidth: "700px",
		fontSize: "16px",
		fontFamily: "Arial",
		lineHeight: 1.3
	}

	headerStyle = {
		fontSize: "35px",
		marginTop: "30px",
		marginBottom: "30px",
	}

	constructor(props) {
		super(props)
		this.state = {
			units: [],
			isWaitingForResults: false,
			searchText: "",
			errorMessage: "",
			examplePlaceholder: this.examplePlaceholder(),
		}
	}

	examplePlaceholder() {
		var randIdx = Math.floor(Math.random() * exampleQueries.length)
		var examplePlaceholder = "e.g. " + exampleQueries[randIdx]
		return examplePlaceholder
	}

	search() {
		this.setState({isWaitingForResults: true})
		this.setState({examplePlaceholder: this.examplePlaceholder()})
		fetchFromServer(API_URL, {"sentence": this.state.searchText}).then(res => {
			this.setState({units: res.textUnits, error: "", isWaitingForResults: false})
		}).catch(err => {
			var errorMessage = (err.response && err.response.data.msg) || "Error calling API"
			this.setState({isWaitingForResults: false, errorMessage})
		})
	}
	render() {
		var updateSearchText = e => this.setState({searchText: e.target.value})
		var submitSearch = e => {e.preventDefault(); this.search()}
		return (
		 <div style={{height: "100%", display: "flex", justifyContent: "center"}}>
			 <div style={this.style}>
				 {this.state.errorMessage && this.state.errorMessage}
				 <div style={this.headerStyle}>Forum</div>
				 <div style={{marginBottom: "20px"}}>
					 <SearchBar
						 onSubmit={submitSearch}
						 onChange={updateSearchText}
						 disabled={this.state.isWaitingForResults}
						 placeholder={this.state.examplePlaceholder}
						 value={this.state.searchText}
						 isLoading={this.state.isWaitingForResults}
						/>
				 </div>
				 {this.state.units.map(unit => <ResultItem key={unit.vectorNum} unit={unit} />)}
				<div style={{marginTop: "30px", marginBottom: "30px", border: "1px solid #fff", borderRadius: "4px", padding: "5px"}}>
					Search news headlines.
				</div>
			 </div>
		 </div>
		)
	}

}

class SearchBar extends React.Component{

	style = {
		borderRadius: "4px",
		width: "100%",
		boxShadow: "0px 1px 4px #ccc",
		boxSizing: "border-box",
		display: "flex",
	}

	inputStyle = {
		borderRadius: "4px",
		border: "none",
		outline: "none",
		padding: "10px",
		fontFamily: "inherit",
		fontSize: "inherit",
		width: "100%",
		backgroundColor: "white",
	}

  constructor(props){
    super(props);
  }

  render() {
    return (
      <div style={this.style}>
        <form onSubmit={this.props.onSubmit} style={{margin: 0, width: "100%"}}>
          <input style={this.inputStyle}
						placeholder={this.props.placeholder}
						onChange={this.props.onChange}
						disabled={this.props.disabled}
						value={this.props.value}
					/>
        </form>
				<div style={{display: "flex", justifyContent: "center", alignItems: "center", paddingRight: "5px"}}>
					<LoadingIndicator isLoading={this.props.isLoading} onClicked={this.props.onSubmit} />
				</div>
      </div>
    )
  }
}

class ResultItem extends React.Component {

	style = {
		// boxShadow: "0px 0px 3px #ccc",
		padding: "20px",
		paddingTop: "20px",
		paddingBottom: "20px",
		borderRadius: "4px",
	}

	textAreaStyle = {
		padding: "5px",
		paddingRight: "15px", //scroll bar space
	}

	infoStringStyle = {
		marginTop: "20px",
		textAlign: "right",
		fontSize: "16px",
		width: "60%",
		padding: "5px",
		borderRadius: "5px",
		border: "1px solid #000",
	}

	constructor(props) {
		super(props)
		this.state = {
			expanded: false,
			hovering: false,
			isLoading: false,
			units: [this.props.unit],
		}
		this.textAreaRef = React.createRef()
	}

	range(start, end) {
		var range = []
		for (var i=start; i<end; i++) {
			range.push(i)
		}
		return range
	}

	render() {
		var unit = this.props.unit
		var onHover = e => this.setState({hovering: true})
		var onUnHover = e => this.setState({hovering: false})
		var onClick = e => {
			// this.setState({expanded: true})
		}
		// var onClick = e => this.setState(state => ({expanded: !state.expanded}))
		var hoverStyle = this.state.hovering ? {} : {}
		var expandedStyle = this.state.expanded ? {height: "80%", overflow: "auto"} : {}
		var infoDiv = <div style={this.infoStringStyle}>{"potatoes"}</div>
		var date = new Date(unit.TIMESTAMP) // all 2014 on current csv, so don't show for now

		//can make heuristic: table of contents (e.g. search "test12345") have a bunch of em dashes in them.
		// So say if the number of dashes exceeds ten, then break at those dashes.

		return (
			<React.Fragment>
				<div style={{...this.style, ...hoverStyle}} onMouseOver={onHover} onMouseLeave={onUnHover}>
					<div onClick={onClick} ref={this.textAreaRef} style={{...this.textAreaStyle, ...expandedStyle}}>
						<a style={{color: "#333"}} href={unit.URL}>{unit.TITLE}</a> – {unit.PUBLISHER}
					</div>
					<div style={{display: "flex", justifyContent: "flex-end"}}>
						{this.state.expanded && infoDiv}
					</div>
				</div>
				<div style={{width: "100%", border: "none", height: "1px", backgroundColor: "#ccc"}}/>
			</React.Fragment>
		)
	}
}

class LoadingIndicator extends React.Component {

	containerStyle = {
		display: "flex",
		justifyContent: "center",
		alignItems: "center",
		backgroundColor:"white",
		borderRadius:"50%",
		height:"30px",
		width:"30px",
		cursor: "pointer",
	}

  constructor(props) {
    super(props)
    this.iconRef = React.createRef()
  }

  updateAnimation() {
    if (this.props.isLoading) {
      this.iconRef.current.style.animationPlayState = "running"
    }
    else {
      this.iconRef.current.style.animationPlayState = "paused"
    }
  }

  componentDidMount() {
    this.iconRef.current.style.animation = "rotating 0.5s linear infinite"
    this.updateAnimation()
  }
  componentDidUpdate() {
    this.updateAnimation()
  }

  render() {
    var active = true
    return (
      <div ref={this.iconRef} onClick={this.props.onClicked} style={this.containerStyle}>
        <div author="Loading icon by aurer: https://codepen.io/aurer/pen/jEGbA" title="0">
          <svg version="1.1" id="loader-1" x="0px" y="0px"
           width="30px" height="30px" viewBox="0 0 40 40" enableBackground="new 0 0 40 40" space="preserve">
            <path opacity="0.2" fill="#000" d="M20.201,5.169c-8.254,0-14.946,6.692-14.946,14.946c0,8.255,6.692,14.946,14.946,14.946
              s14.946-6.691,14.946-14.946C35.146,11.861,28.455,5.169,20.201,5.169z M20.201,31.749c-6.425,0-11.634-5.208-11.634-11.634
              c0-6.425,5.209-11.634,11.634-11.634c6.425,0,11.633,5.209,11.633,11.634C31.834,26.541,26.626,31.749,20.201,31.749z"/>
            <path fill="#000" d="M26.013,10.047l1.654-2.866c-2.198-1.272-4.743-2.012-7.466-2.012h0v3.312h0
              C22.32,8.481,24.301,9.057,26.013,10.047z">
            </path>
          </svg>
        </div>
      </div>
    )
  }

}

ReactDOM.render(<App />, document.getElementById('root'));
